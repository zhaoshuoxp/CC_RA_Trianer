"""Chinese desktop UI. No game files are modified."""
import ctypes as C,ctypes.wintypes as W,threading,queue,time,json,sys,traceback
from pathlib import Path
import tkinter as tk
from tkinter import ttk,messagebox
from engine import Trainer,FEATURES

class App:
 def __init__(self,root):
  self.root=root;self.t=Trainer();self.jobs=queue.Queue();self.events=queue.Queue();self.connected=False;self.pid=0;self.closing=False;self.polling=False
  self.user=C.WinDLL('user32');self.user.GetForegroundWindow.restype=W.HWND
  self.user.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
  self.user.SetForegroundWindow.argtypes=[W.HWND]
  self.user.EnumWindows.argtypes=[C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM),W.LPARAM]
  self.hot_down=set()
  scale=max(1.0,root.winfo_fpixels('1i')/96)
  width=min(round(690*scale),root.winfo_screenwidth()-80);height=min(round(755*scale),root.winfo_screenheight()-100)
  root.title('尤里的复仇 · 单人修改器');root.geometry(f'{width}x{height}');root.minsize(min(width,round(670*scale)),min(height,round(720*scale)))
  root.configure(bg='#17202b');root.protocol('WM_DELETE_WINDOW',self.close)
  st=ttk.Style(root);st.theme_use('clam')
  st.configure('.',font=('Microsoft YaHei UI',10),background='#17202b',foreground='#e3eaf1')
  st.configure('TButton',background='#30445a',foreground='white',padding=(10,7),borderwidth=0)
  st.map('TButton',background=[('active','#416483')])
  st.configure('TCheckbutton',background='#17202b',foreground='#e3eaf1',padding=5)
  st.map('TCheckbutton',background=[('active','#243449')])
  st.configure('TEntry',fieldbackground='#f4f6f8',foreground='#17202b',padding=5)
  st.configure('TLabelframe',background='#17202b',bordercolor='#3e5369')
  st.configure('TLabelframe.Label',font=('Microsoft YaHei UI',10,'bold'),foreground='#9fc7ed')
  st.configure('Treeview',background='#1d2b3a',fieldbackground='#1d2b3a',foreground='#e3eaf1',rowheight=round(26*scale))
  st.configure('Treeview.Heading',background='#30445a',foreground='white')
  top=ttk.Frame(root,padding=(20,15,20,5));top.pack(fill='x')
  ttk.Label(top,text='尤里的复仇',font=('Microsoft YaHei UI',22,'bold')).pack(anchor='w')
  ttk.Label(top,text='CnCNet 9.3.3  ·  Ares 3.0p1  ·  Phobos 0.4.0.2',foreground='#9faebd').pack(anchor='w',pady=(2,10))
  bar=ttk.Frame(top);bar.pack(fill='x')
  self.connect_btn=ttk.Button(bar,text='连接游戏',command=self.connect);self.connect_btn.pack(side='left')
  ttk.Button(bar,text='关闭全部功能',command=self.disable_all).pack(side='left',padx=8)
  self.topmost=tk.BooleanVar(value=False);ttk.Checkbutton(bar,text='窗口置顶',variable=self.topmost,command=lambda:root.attributes('-topmost',self.topmost.get())).pack(side='right')
  root.attributes('-topmost',False)
  self.stats=tk.StringVar(value='先在 CnCNet 中进入单人战役或遭遇战，再连接。')
  ttk.Label(top,textvariable=self.stats,foreground='#80d3bd').pack(anchor='w',pady=(10,4))
  body=ttk.Frame(root,padding=(20,0,20,0));body.pack(fill='both',expand=True)
  money=ttk.LabelFrame(body,text='金钱与电力',padding=10);money.pack(fill='x',pady=6)
  self.money=tk.StringVar(value='100000');self.power=tk.StringVar(value='100000')
  ttk.Label(money,text='金额').grid(row=0,column=0,sticky='w')
  ttk.Entry(money,textvariable=self.money,width=13).grid(row=0,column=1,padx=8)
  ttk.Button(money,text='设置',command=lambda:self.change_money(False)).grid(row=0,column=2,padx=3)
  ttk.Button(money,text='增加',command=lambda:self.change_money(True)).grid(row=0,column=3,padx=3)
  self.vars={k:tk.BooleanVar(value=False) for k in FEATURES}
  ttk.Checkbutton(money,text='保持至少此金额',variable=self.vars['money'],command=lambda:self.toggle('money')).grid(row=0,column=4,padx=5)
  ttk.Label(money,text='额外供电').grid(row=1,column=0,sticky='w',pady=(10,0))
  ttk.Entry(money,textvariable=self.power,width=13).grid(row=1,column=1,padx=8,pady=(10,0))
  ttk.Checkbutton(money,text='启用额外供电',variable=self.vars['power'],command=lambda:self.toggle('power')).grid(row=1,column=2,columnspan=2,sticky='w',pady=(10,0))
  ttk.Button(money,text='应用供电值',command=lambda:self.toggle('power')).grid(row=1,column=4,pady=(10,0))
  build=ttk.LabelFrame(body,text='建造与地图',padding=8);build.pack(fill='x',pady=6)
  for i,(key,label) in enumerate([('buildings','建筑瞬间建造'),('tech','全科技'),('placement','远距离放置')]):
   ttk.Checkbutton(build,text=label,variable=self.vars[key],command=lambda k=key:self.toggle(k)).grid(row=0,column=i,padx=4)
  ttk.Button(build,text='地图全开  小键盘6',command=lambda:self.unit(10,'地图全开')).grid(row=0,column=3,padx=5)
  ttk.Checkbutton(build,text='我方超武无冷却',variable=self.vars['super'],command=lambda:self.toggle('super')).grid(row=1,column=0,columnspan=2,sticky='w')
  ttk.Button(build,text='我方超武立即就绪  小键盘+',command=lambda:self.unit(11,'我方超武立即就绪')).grid(row=1,column=2,columnspan=2,pady=4)
  ttk.Checkbutton(build,text='单位快速生产（约1秒）',variable=self.vars['units'],command=lambda:self.toggle('units')).grid(row=2,column=0,columnspan=2,sticky='w')
  ttk.Label(build,text='54游戏帧；出厂堵塞仍需等待。',foreground='#9faebd').grid(row=2,column=2,columnspan=2,sticky='w')
  units=ttk.LabelFrame(body,text='所选单位',padding=10);units.pack(fill='both',expand=True,pady=6)
  buttons=ttk.Frame(units);buttons.pack(fill='x')
  for text,cmd in [('恢复生命',3),('加入无敌',4),('移除无敌',5),('单位归我',6),('清空保护',7)]:
   ttk.Button(buttons,text=text,command=lambda c=cmd,n=text:self.unit(c,n)).pack(side='left',padx=(0,5))
  ttk.Label(units,text='加入无敌后，取消选择仍有效。读档或新开局会清空保护。',foreground='#9faebd').pack(anchor='w',pady=7)
  self.tree=ttk.Treeview(units,columns=('type','hp','owner','protect'),show='headings',height=5)
  for key,text,width in [('type','单位',130),('hp','生命',130),('owner','归属',95),('protect','保护',95)]:
   self.tree.heading(key,text=text);self.tree.column(key,width=width,anchor='center')
  self.tree.pack(fill='both',expand=True)
  ttk.Label(body,text='小键盘（Num Lock 开）：1 加钱 · 2 供电 · 3 回血 · 4 无敌 · 5 归我\n6 地图 · 7 建筑瞬建 · 8 全科技 · 9 远建 · 0 清空保护\n− 单位快产 · + 超武就绪 · 小数点 超武无冷却',foreground='#9faebd').pack(anchor='w',pady=(8,4))
  self.status=tk.StringVar(value='未连接');ttk.Label(root,textvariable=self.status,wraplength=round(625*scale),foreground='#f1d49a',padding=(20,8)).pack(fill='x')
  threading.Thread(target=self.worker,daemon=True).start();root.after(100,self.pump);root.after(600,self.poll)
 def worker(self):
  while True:
   name,fn=self.jobs.get()
   try:self.events.put((name,True,fn()))
   except Exception as e:self.events.put((name,False,str(e)))
   if name=='close':return
 def submit(self,name,fn):self.jobs.put((name,fn))
 def action(self,name,fn):
  if not self.connected:self.status.set('请先连接已进入地图的游戏。');return
  self.status.set(name+'…');self.submit(name,fn)
 def connect(self):
  if self.connected:self.submit('disconnect',self.t.detach)
  else:self.status.set('正在核对游戏版本…');self.submit('connect',self.t.attach)
 def unit(self,cmd,name):self.action(name,lambda:self.t.command(cmd))
 def change_money(self,add):
  try:value=int(self.money.get())
  except ValueError:self.status.set('请输入整数金额。');return
  self.action('增加金钱' if add else '设置金钱',lambda:self.t.set_money(value,add))
 def toggle(self,key):
  enabled=self.vars[key].get();value=None
  try:
   if key=='money':value=int(self.money.get())
   if key=='power':value=int(self.power.get())
  except ValueError:self.status.set('请输入整数。');return
  self.action('更新功能',lambda:self.t.feature(key,enabled,value))
 def disable_all(self):
  def off():
   for key in FEATURES:self.t.feature(key,False)
   self.t.command(7)
  self.action('关闭全部功能',off)
 def poll(self):
  if self.connected and not self.polling and not self.closing:
   self.polling=True;self.submit('snapshot',self.t.snapshot)
  if not self.closing:self.root.after(600,self.poll)
 def pump(self):
  while not self.events.empty():
   name,ok,result=self.events.get()
   if name=='close':self.root.destroy();return
   if name=='snapshot':self.polling=False
   if not ok:
    self.status.set(result)
    if name in ('snapshot','connect'):
     self.connected=False;self.pid=0;self.connect_btn.configure(text='连接游戏');self.submit('cleanup',self.t.detach)
    continue
   if name=='connect':self.connected=True;self.pid=result['pid'];self.connect_btn.configure(text='断开并恢复');self.status.set('已连接；功能默认关闭。')
   if name=='disconnect':self.connected=False;self.pid=0;self.connect_btn.configure(text='连接游戏');self.status.set('已恢复补丁并断开。')
   if name in ('snapshot','connect'):
    s=result;self.stats.set(f"金钱 {s['money']:,}    电力 {s['power']:,} / {s['drain']:,}    已保护 {s['protected']} 个")
    for key,mask in FEATURES.items():self.vars[key].set(bool(s['flags']&mask))
    self.tree.delete(*self.tree.get_children())
    for x in s['selected']:self.tree.insert('',tk.END,values=(x['name'],f"{x['hp']} / {x['maxhp']}",'我方' if x['owner']==s['player'] else '其他','无敌' if x.get('protected') else '—'))
   elif name not in ('cleanup','disconnect'):self.status.set(name+'：已完成'+(f'，处理 {result} 个目标' if isinstance(result,int) and result>0 else ''))
  self.hotkeys()
  if not self.closing:self.root.after(80,self.pump)
 def hotkeys(self):
  # Edge-triggered polling never activates a window or installs global key hooks.
  down={vk for vk in [*range(0x60,0x6A),0x6B,0x6D,0x6E] if self.user.GetAsyncKeyState(vk)&0x8000}
  pressed=down-self.hot_down;self.hot_down=down
  if not self.connected or not pressed:return
  fg=self.user.GetForegroundWindow();p=W.DWORD();self.user.GetWindowThreadProcessId(fg,C.byref(p))
  # Do not trigger actions while entering amounts in the trainer or typing in other apps.
  if p.value!=self.pid:return
  if any(self.user.GetAsyncKeyState(vk)&0x8000 for vk in (0x10,0x11,0x12)):return
  for vk in sorted(pressed):
   key=vk-0x60
   if key==1:self.change_money(True)
   elif key in (2,7,8,9,13,14):
    k={2:'power',7:'buildings',8:'tech',9:'placement',13:'units',14:'super'}[key];self.vars[k].set(not self.vars[k].get());self.toggle(k)
   else:
    c,n={0:(7,'清空保护'),3:(3,'恢复生命'),4:(4,'加入无敌'),5:(6,'单位归我'),6:(10,'地图全开'),11:(11,'我方超武立即就绪')}[key];self.unit(c,n)
 def close(self):
  if self.closing:return
  self.closing=True;self.status.set('正在恢复补丁…');self.submit('close',self.t.detach);self.root.after(100,self.pump)

if __name__=='__main__':
 C.WinDLL('user32').SetProcessDPIAware()
 if '--check' in sys.argv:
  from engine import asm
  assert asm('ret',0x100000)==b'\xc3'
  assert len(json.loads((Path(__file__).parent/'fingerprints.json').read_text(encoding='utf-8-sig')))==6
  sys.exit(0)
 App(tk.Tk()).root.mainloop()
