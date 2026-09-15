"""Local single-player Yuri's Revenge trainer. All engine calls execute in its game thread."""
import json,hashlib,struct,time
from pathlib import Path
from winmem import Mem,processes,modules
from keystone import Ks,KS_ARCH_X86,KS_MODE_32

ROOT=Path(__file__).resolve().parent
PLAYER=0xA83D4C; FRAME=0xA8ED84; MODE=0xA8B238; SELECT=0xA8ECB8
FLAGS=0x08; CMD=0x0C; ARG=0x10; ACK=0x14; RESULT=0x18; COUNT=0x1C
MONEY=0x20; POWER=0x24; HEART=0x28; LASTFRAME=0x2C; LASTPLAYER=0x30
TECHCOUNT=0x34; BUSY=0x38; GENERATION=0x3C; ENABLED=0x40
PROTECTED=0x100; SNAPSHOT=0x1100; TECHS=0x1600; LIMIT=256
FEATURES={'money':1,'power':2,'buildings':4,'tech':8,'placement':16,'super':32,'units':64}
ALLOWED=set('''GAPOWR GAREFN GAPILE GAWEAP GADEPT GATECH GAYARD GAAIRC AMRADR GAWALL GAPILL NASAM ATESLA GTGCAN GASPYSAT GAGAP GAOREP GACSPH GAWEAT
NAPOWR NAREFN NAHAND NAWEAP NARADR NATECH NAYARD NADEPT NAWALL NALASR NAFLAK TESLA NABNKR NANRCT NAINDP NAIRON NAMISL
YAPOWR YAREFN YABRCK YAWEAP NAPSIS YATECH YAYARD NACLON YAGNTC YAGRND GAFWLL YAGGUN YAPSYT NATBNK YAPPET YAGNTC
E1 GGI ENGINEER JUMPJET SNIPE SPY GHOST CLEG CCOMAND ADOG E2 SHK FLAKT IVAN TERROR DESO DOG SENGINEER BORIS INIT YURI BRUTE VIRUS YURIP YENGINEER
AMCV MCV PCV MTNK FV LCRF TNKD TD V3 HTNK HARV CMIN MGTK SREF APOC DTRUCK HTK HTKR DRON YTNK LTNK TELE SMIN MIND DISK SAPC CMON SMON ROBOT CAOS SCHP DRED SUB HYD DEST AEGIS CARRIER DLPH SQD BSUB ORCA BEAG ZEP SHAD'''.split())

def asm(code,addr):
 try:return bytes(Ks(KS_ARCH_X86,KS_MODE_32).asm(code,addr)[0])
 except Exception as e:
  raise RuntimeError(f'Assembler failed near statement {getattr(e,"stat_count",None)}: {e}') from e
def jump(src,dst,n=5):return b'\xE9'+struct.pack('<I',(dst-src-5)&0xffffffff)+b'\x90'*(n-5)
def vector(m,a,maximum=10000):
 count=m.i32(a+16);capacity=m.i32(a+8);data=m.u32(a+4)
 if not 0<=count<=capacity<=maximum:raise RuntimeError('Invalid game collection')
 if count and data<0x10000:raise RuntimeError('Invalid collection pointer')
 return list(struct.unpack('<'+'I'*count,m.read(data,count*4))) if count else []

class Trainer:
 def __init__(self):self.mem=None;self.base=0;self.patches=[];self.types={};self.last_generation=-1;self.last_prune=0
 def find(self):
  games=[p for p in processes() if p[1].lower()=='gamemd-spawn.exe']
  if len(games)!=1:raise RuntimeError('请先进入一个 CnCNet 单人战役或遭遇战（gamemd-spawn.exe）。')
  return games[0][0]
 def attach(self,pid=None):
  if self.mem:self.detach()
  pid=pid or self.find();mods=modules(pid)
  byname={x['name'].lower():x for x in mods}
  wanted={x['Name'].lower():x['SHA256'] for x in json.loads((ROOT/'fingerprints.json').read_text(encoding='utf-8-sig'))}
  for name in ['gamemd-spawn.exe','ares.dll','phobos.dll','cncnet-spawner.dll']:
   mod=byname.get(name)
   if not mod:raise RuntimeError('缺少已验证模块：'+name)
   if hashlib.sha256(Path(mod['path']).read_bytes()).hexdigest().upper()!=wanted[name]:
    raise RuntimeError('版本指纹不同，停止写入：'+name)
  if byname['gamemd-spawn.exe']['base']!=0x400000:raise RuntimeError('不支持的映像基址')
  self.mem=Mem(pid);self.path=byname['gamemd-spawn.exe']['path']
  try:
   self.validate_session();self.build_types()
   self.install()
  except Exception:
   self.detach();raise
  return self.snapshot()
 def validate_session(self):
  m=self.mem
  if m.u32(MODE) not in (0,5):raise RuntimeError('此版本只支持单人战役和离线遭遇战。')
  p=m.u32(PLAYER)
  houses=vector(m,0xA80228,64)
  if p not in houses or m.read(p+0x1EC,1)!=b'\1':raise RuntimeError('请进入地图后再连接。')
  if sum(m.read(h+0x1ec,1)==b'\1' for h in houses)>1:raise RuntimeError('当前存在多个真人玩家，未启用修改。')
  if not -100000000<=m.i32(p+0x30c)<=100000000:raise RuntimeError('玩家字段验证失败')
  return p
 def build_types(self):
  self.types={};self.allowed=[]
  for a in [0xA83C68,0xA83CE0,0xA8E348,0xA8B218]:
   for ptr in vector(self.mem,a,4096):
    ident=self.mem.read(ptr+0x24,24).split(b'\0')[0].decode('ascii','replace')
    self.types[ptr]=(ident,self.mem.i32(ptr+0xA0))
    if ident in ALLOWED:self.allowed.append(ptr)
 def install(self):
  m=self.mem;self.patches=[]
  checks={0x5D4D50:bytes.fromhex('A1 50 35 B7 00'),0x5F5509:bytes.fromhex('2B C2 85 C0 89 46 6C'),
   0x508D7F:bytes.fromhex('8B CE E8 5A BF F4 FF'),0x4A8EB0:bytes.fromhex('A1 4C 3D A8 00'),
   0x67E440:bytes.fromhex('81 EC 08 05 00 00'),0x683AB0:bytes.fromhex('81 EC EC 00 00 00')}
  for a,expected in checks.items():
   if m.read(a,len(expected))!=expected:raise RuntimeError(f'补丁冲突，未安装：{a:08X}')
  original_tech=m.read(0x4F7870,7)
  if original_tech[0]!=0xE9:raise RuntimeError('全科技扩展入口与已验证版本不同')
  tech_previous=0x4F7875+struct.unpack('<i',original_tech[1:5])[0]
  if tech_previous<0x10000:raise RuntimeError('无效扩展跳转')
  self.base=b=m.alloc(0x10000)
  data=bytearray(0x2000);struct.pack_into('<I',data,0,0x59525431)
  struct.pack_into('<I',data,MONEY,100000);struct.pack_into('<I',data,POWER,100000)
  struct.pack_into('<I',data,ENABLED,1)
  struct.pack_into('<I',data,TECHCOUNT,len(self.allowed))
  for i,p in enumerate(self.allowed):struct.pack_into('<I',data,TECHS+i*4,p)
  m.write(b,data)
  def at(x):return hex(b+x)
  f=at(FLAGS);enabled=at(ENABLED)
  tick=f'''
pushfd
pushad
cmp dword ptr [{at(BUSY)}],0
jne tick_out
mov dword ptr [{at(BUSY)}],1
inc dword ptr [{at(HEART)}]
cmp dword ptr [{enabled}],1
jne tick_done
mov eax,dword ptr [{MODE}]
cmp eax,0
je tick_mode_ok
cmp eax,5
jne reset_session
tick_mode_ok:
mov ebp,dword ptr [{PLAYER}]
test ebp,ebp
jz reset_session
cmp byte ptr [ebp+0x1EC],1
jne reset_session
mov eax,dword ptr [{FRAME}]
cmp ebp,dword ptr [{at(LASTPLAYER)}]
jne new_session
cmp eax,dword ptr [{at(LASTFRAME)}]
jb new_session
jmp session_ready
new_session:
mov dword ptr [{at(COUNT)}],0
inc dword ptr [{at(GENERATION)}]
session_ready:
mov dword ptr [{at(LASTFRAME)}],eax
mov dword ptr [{at(LASTPLAYER)}],ebp
test dword ptr [{f}],1
jz money_done
mov eax,dword ptr [{at(MONEY)}]
cmp dword ptr [ebp+0x30C],eax
jge money_done
mov dword ptr [ebp+0x30C],eax
money_done:
test dword ptr [{f}],68
jz instant_done
mov edi,dword ptr [0xA83E40]
cmp edi,4096
ja instant_done
cmp edi,dword ptr [0xA83E38]
ja instant_done
mov esi,dword ptr [0xA83E34]
test esi,esi
jz instant_done
xor ebx,ebx
factory_loop:
cmp ebx,edi
jae instant_done
mov ecx,dword ptr [esi+ebx*4]
test ecx,ecx
jz next_factory
cmp dword ptr [ecx+0x6C],ebp
jne next_factory
cmp byte ptr [ecx+0x70],0
jne next_factory
cmp dword ptr [ecx+0x38],0
jle next_factory
mov eax,dword ptr [ecx+0x58]
test eax,eax
jz next_factory
cmp dword ptr [eax+0x21C],ebp
jne next_factory
mov eax,dword ptr [eax]
cmp eax,0x7E3EBC
je building_factory
cmp eax,0x7F5C70
je unit_factory
cmp eax,0x7EB058
je unit_factory
cmp eax,0x7E22A4
jne next_factory
unit_factory:
test dword ptr [{f}],64
jz next_factory
cmp dword ptr [ecx+0x24],54
jge next_factory
mov dword ptr [ecx+0x34],0
jmp next_factory
building_factory:
test dword ptr [{f}],4
jz next_factory
cmp dword ptr [ecx+0x24],54
jge next_factory
mov dword ptr [ecx+0x24],53
mov byte ptr [ecx+0x28],1
mov byte ptr [ecx+0x5D],1
mov dword ptr [ecx+0x34],0
next_factory:
inc ebx
jmp factory_loop
instant_done:
test dword ptr [{f}],32
jz super_done
call charge_supers
super_done:
mov eax,dword ptr [{at(CMD)}]
test eax,eax
jz tick_done
mov dword ptr [{at(RESULT)}],0
cmp eax,1
je set_money
cmp eax,2
je add_money
cmp eax,7
je clear_protect
cmp eax,8
je refresh_power
cmp eax,9
je refresh_tech
cmp eax,10
je reveal_map
cmp eax,11
je refresh_supers
mov ecx,dword ptr [{SELECT+16}]
cmp ecx,256
ja bad_selection
mov esi,dword ptr [{SELECT+4}]
mov edi,{at(SNAPSHOT)}
mov ebx,ecx
cld
rep movsd dword ptr es:[edi], dword ptr [esi]
xor edi,edi
selection_loop:
cmp edi,ebx
jae command_done
mov esi,dword ptr [{at(SNAPSHOT)}+edi*4]
test esi,esi
jz next_selected
test dword ptr [esi+0x14],1
jz next_selected
cmp byte ptr [esi+0x90],0
je next_selected
mov eax,dword ptr [{at(CMD)}]
cmp eax,3
je heal_selected
cmp eax,4
je protect_selected
cmp eax,5
je unprotect_selected
cmp eax,6
je capture_selected
jmp next_selected
heal_selected:
mov ecx,esi
mov eax,dword ptr [esi]
call dword ptr [eax+0x84]
test eax,eax
jz next_selected
mov eax,dword ptr [eax+0xA0]
test eax,eax
jle next_selected
mov dword ptr [esi+0x6C],eax
mov dword ptr [esi+0x70],eax
inc dword ptr [{at(RESULT)}]
jmp next_selected
protect_selected:
xor ecx,ecx
mov edx,dword ptr [esi+0x10]
find_existing:
cmp ecx,dword ptr [{at(COUNT)}]
jae add_protected
cmp dword ptr [{at(PROTECTED)}+ecx*8],esi
jne find_next
cmp dword ptr [{at(PROTECTED+4)}+ecx*8],edx
je next_selected
find_next:
inc ecx
jmp find_existing
add_protected:
cmp ecx,256
jae next_selected
mov dword ptr [{at(PROTECTED)}+ecx*8],esi
mov dword ptr [{at(PROTECTED+4)}+ecx*8],edx
inc dword ptr [{at(COUNT)}]
inc dword ptr [{at(RESULT)}]
jmp next_selected
unprotect_selected:
xor ecx,ecx
remove_loop:
cmp ecx,dword ptr [{at(COUNT)}]
jae next_selected
cmp dword ptr [{at(PROTECTED)}+ecx*8],esi
jne remove_next
mov edx,dword ptr [esi+0x10]
cmp dword ptr [{at(PROTECTED+4)}+ecx*8],edx
jne remove_next
dec dword ptr [{at(COUNT)}]
mov edx,dword ptr [{at(COUNT)}]
mov eax,dword ptr [{at(PROTECTED)}+edx*8]
mov dword ptr [{at(PROTECTED)}+ecx*8],eax
mov eax,dword ptr [{at(PROTECTED+4)}+edx*8]
mov dword ptr [{at(PROTECTED+4)}+ecx*8],eax
inc dword ptr [{at(RESULT)}]
jmp next_selected
remove_next:
inc ecx
jmp remove_loop
capture_selected:
cmp dword ptr [esi+0x21C],ebp
je next_selected
push 1
push ebp
mov ecx,esi
mov eax,dword ptr [esi]
call dword ptr [eax+0x3D4]
test al,al
jz next_selected
inc dword ptr [{at(RESULT)}]
mov byte ptr [ebp+0x1FA],1
mov byte ptr [ebp+0x5778],1
next_selected:
inc edi
jmp selection_loop
set_money:
mov eax,dword ptr [{at(ARG)}]
mov dword ptr [ebp+0x30C],eax
jmp command_done
add_money:
mov eax,dword ptr [{at(ARG)}]
add dword ptr [ebp+0x30C],eax
jmp command_done
clear_protect:
mov dword ptr [{at(COUNT)}],0
jmp command_done
refresh_power:
mov ecx,ebp
call 0x508C30
jmp command_done
refresh_tech:
mov byte ptr [ebp+0x1FA],1
jmp command_done
refresh_supers:
call charge_supers
mov dword ptr [{at(RESULT)}],eax
jmp command_done
reveal_map:
push ebp
mov ecx,0x87F7E8
call 0x577D90
mov dword ptr [{at(RESULT)}],1
jmp command_done
charge_supers:
push ebx
push esi
push edi
xor edi,edi
mov ebx,dword ptr [0xA83CC8]
cmp ebx,4096
ja supers_exit
cmp ebx,dword ptr [0xA83CC0]
ja supers_exit
mov esi,dword ptr [0xA83CBC]
test esi,esi
jz supers_exit
supers_loop:
test ebx,ebx
jz supers_exit
mov ecx,dword ptr [esi]
test ecx,ecx
jz supers_next
cmp dword ptr [ecx+0x2C],ebp
jne supers_next
cmp byte ptr [ecx+0x6D],1
jne supers_next
cmp byte ptr [ecx+0x70],0
jne supers_next
cmp dword ptr [ecx+0x7C],2
je supers_next
cmp byte ptr [ecx+0x6F],0
je expire_super
cmp dword ptr [ecx+0x38],0
jne expire_super
cmp dword ptr [ecx+0x7C],0
jne supers_next
expire_super:
mov eax,dword ptr [{FRAME}]
mov dword ptr [ecx+0x30],eax
mov dword ptr [ecx+0x38],0
mov byte ptr [ecx+0x6F],0
push 0
call 0x6CBCA0
inc edi
supers_next:
add esi,4
dec ebx
jmp supers_loop
supers_exit:
mov eax,edi
pop edi
pop esi
pop ebx
ret
bad_selection:
mov dword ptr [{at(RESULT)}],0xFFFFFFFF
command_done:
mov dword ptr [{at(CMD)}],0
inc dword ptr [{at(ACK)}]
jmp tick_done
reset_session:
mov dword ptr [{at(COUNT)}],0
mov dword ptr [{at(LASTPLAYER)}],0
mov dword ptr [{f}],0
mov dword ptr [{at(CMD)}],0
tick_done:
mov dword ptr [{at(BUSY)}],0
tick_out:
popad
popfd
mov eax,dword ptr [0xB73550]
jmp 0x5D4D55
'''
  god=f'''
cmp dword ptr [{enabled}],1
jne god_original
test edx,edx
jle god_original
push ecx
push ebx
xor ecx,ecx
mov ebx,dword ptr [esi+0x10]
god_loop:
cmp ecx,dword ptr [{at(COUNT)}]
jae god_pop
cmp dword ptr [{at(PROTECTED)}+ecx*8],esi
jne god_next
cmp dword ptr [{at(PROTECTED+4)}+ecx*8],ebx
jne god_next
xor edx,edx
jmp god_pop
god_next:
inc ecx
jmp god_loop
god_pop:
pop ebx
pop ecx
god_original:
sub eax,edx
test eax,eax
mov dword ptr [esi+0x6C],eax
jmp 0x5F5510
'''
  power=f'''
pushfd
push eax
cmp dword ptr [{enabled}],1
jne power_original
test dword ptr [{f}],2
jz power_original
cmp esi,dword ptr [{PLAYER}]
jne power_original
mov eax,dword ptr [{at(POWER)}]
add dword ptr [esi+0x53A4],eax
power_original:
pop eax
popfd
mov ecx,esi
call 0x454CE0
jmp 0x508D86
'''
  tech=f'''
cmp dword ptr [{enabled}],1
jne tech_original
test dword ptr [{f}],8
jz tech_original
cmp ecx,dword ptr [{PLAYER}]
jne tech_original
push edx
push ebx
mov eax,dword ptr [esp+12]
xor edx,edx
tech_loop:
cmp edx,dword ptr [{at(TECHCOUNT)}]
jae tech_not_found
cmp eax,dword ptr [{at(TECHS)}+edx*4]
je tech_allowed
inc edx
jmp tech_loop
tech_allowed:
pop ebx
pop edx
mov eax,1
ret 12
tech_not_found:
pop ebx
pop edx
tech_original:
jmp {tech_previous}
'''
  placement=f'''
cmp dword ptr [{enabled}],1
jne placement_original
test dword ptr [{f}],16
jz placement_original
mov eax,1
ret 16
placement_original:
mov eax,dword ptr [{PLAYER}]
jmp 0x4A8EB5
'''
  specs=[(0x5D4D50,tick,5),(0x5F5509,god,7),(0x508D7F,power,7),(0x4F7870,tech,7),(0x4A8EB0,placement,5)]
  for site,stacksize in [(0x67E440,0x508),(0x683AB0,0xEC)]:
   reset=f'''mov dword ptr [{at(COUNT)}],0;mov dword ptr [{f}],0;
mov dword ptr [{at(TECHCOUNT)}],0;mov dword ptr [{at(CMD)}],0;
mov dword ptr [{at(LASTPLAYER)}],0;inc dword ptr [{at(GENERATION)}];sub esp,{stacksize};jmp {site+6}'''
   specs.append((site,reset,6))
  codeaddr=b+0x3000
  for site,code,size in specs:
   binary=asm(code,codeaddr);m.write(codeaddr,binary)
   self.patches.append((site,m.read(site,size),jump(site,codeaddr,size)))
   codeaddr=(codeaddr+len(binary)+15)&~15
  m.suspend()
  try:
   for a,original,patch in self.patches:
    if m.read(a,len(original))!=original:raise RuntimeError('安装时检测到新的补丁冲突')
   for a,original,patch in self.patches:m.write(a,patch)
  finally:m.resume()
 def command(self,cmd,value=0,timeout=3):
  self.validate_session();m=self.mem;b=self.base
  if m.u32(b+CMD):raise RuntimeError('上一命令尚未执行，请返回游戏继续运行。')
  ack=m.u32(b+ACK)
  m.put32(b+ARG,value);m.put32(b+CMD,cmd)
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   if m.u32(b+ACK)!=ack:return m.i32(b+RESULT)
   time.sleep(.015)
  raise RuntimeError('命令等待游戏继续运行；请关闭游戏菜单、恢复对局。')
 def feature(self,name,on,value=None):
  self.validate_session();m=self.mem;b=self.base;flag=FEATURES[name]
  if value is not None:
   if not 0<=value<=10000000:raise ValueError('数值范围为 0～10000000')
   if name in ('money','power'):m.put32(b+(MONEY if name=='money' else POWER),value)
  bits=m.u32(b+FLAGS);m.put32(b+FLAGS,bits|flag if on else bits&~flag)
  if name=='power':self.command(8)
  if name=='tech':self.command(9)
 def set_money(self,value,add=False):
  if not 0<=value<=10000000:raise ValueError('金额范围为 0～10000000')
  if add and self.snapshot()['money']+value>10000000:raise ValueError('结果金额超过 10000000')
  return self.command(2 if add else 1,value)
 def object_info(self,obj):
  m=self.mem;hp=m.i32(obj+0x6c);v=m.u32(obj);func=m.u32(v+0x84);code=m.read(func,8)
  ptr=0
  if code[:2]==b'\x8b\x81':ptr=m.u32(obj+struct.unpack('<I',code[2:6])[0])
  elif code[:2]==b'\x8b\x41':ptr=m.u32(obj+code[2])
  name,maxhp=self.types.get(ptr,('单位',0))
  return dict(address=obj,id=m.u32(obj+0x10),name=name,hp=hp,maxhp=maxhp,owner=m.u32(obj+0x21c))
 def snapshot(self):
  p=self.validate_session();m=self.mem;b=self.base
  selection=[]
  for ptr in vector(m,SELECT,4096)[:LIMIT]:
   try:
    if m.u32(ptr+0x14)&1:selection.append(self.object_info(ptr))
   except OSError:pass
  generation=m.u32(b+GENERATION) if b else 0
  if generation!=self.last_generation:
   self.build_types()
   if b:
    m.suspend()
    try:
     m.put32(b+TECHCOUNT,0)
     m.write(b+TECHS,struct.pack('<'+'I'*len(self.allowed),*self.allowed))
     m.put32(b+TECHCOUNT,len(self.allowed))
    finally:m.resume()
   self.last_generation=generation
  if b and m.u32(b+COUNT) and time.monotonic()-self.last_prune>2:
   m.suspend()
   try:
    live=set(vector(m,0xA8EC78));kept=[]
    for i in range(min(m.u32(b+COUNT),LIMIT)):
     ptr,uid=struct.unpack('<II',m.read(b+PROTECTED+i*8,8))
     if ptr in live and m.u32(ptr+0x10)==uid and m.read(ptr+0x90,1)==b'\1':kept.append((ptr,uid))
    if kept:m.write(b+PROTECTED,b''.join(struct.pack('<II',*x) for x in kept))
    m.put32(b+COUNT,len(kept))
   finally:m.resume()
   self.last_prune=time.monotonic()
  protected=set()
  if b:
   for i in range(min(m.u32(b+COUNT),LIMIT)):
    protected.add(struct.unpack('<II',m.read(b+PROTECTED+i*8,8)))
  for x in selection:x['protected']=(x['address'],x['id']) in protected
  return dict(pid=m.pid,player=p,money=m.i32(p+0x30c),power=m.i32(p+0x53a4),drain=m.i32(p+0x53a8),
   frame=m.u32(FRAME),selected=selection,protected=m.u32(b+COUNT) if b else 0,flags=m.u32(b+FLAGS) if b else 0,
   heartbeat=m.u32(b+HEART) if b else 0,generation=generation)
 def detach(self):
  m=self.mem
  if not m:return
  try:
   if self.base:
    m.put32(self.base+FLAGS,0);m.put32(self.base+COUNT,0)
    try:self.command(8,timeout=.25)
    except Exception:pass
    m.put32(self.base+ENABLED,0)
   m.suspend()
   try:
    for a,original,patch in reversed(self.patches):
     if m.read(a,len(patch))==patch:m.write(a,original)
   finally:m.resume()
  except OSError:pass
  finally:
   m.close();self.mem=None;self.base=0;self.patches=[];self.last_generation=-1
  # Stubs intentionally remain allocated until game exit: a paused thread may still return through one.
