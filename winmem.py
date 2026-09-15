import ctypes as C, ctypes.wintypes as W, struct, json, sys
from pathlib import Path
k=C.WinDLL('kernel32',use_last_error=True)
class PROCESSENTRY32W(C.Structure):
 _fields_=[('dwSize',W.DWORD),('cntUsage',W.DWORD),('th32ProcessID',W.DWORD),('th32DefaultHeapID',C.c_size_t),('th32ModuleID',W.DWORD),('cntThreads',W.DWORD),('th32ParentProcessID',W.DWORD),('pcPriClassBase',W.LONG),('dwFlags',W.DWORD),('szExeFile',W.WCHAR*260)]
class MODULEENTRY32W(C.Structure):
 _fields_=[('dwSize',W.DWORD),('th32ModuleID',W.DWORD),('th32ProcessID',W.DWORD),('GlblcntUsage',W.DWORD),('ProccntUsage',W.DWORD),('modBaseAddr',C.c_void_p),('modBaseSize',W.DWORD),('hModule',W.HMODULE),('szModule',W.WCHAR*256),('szExePath',W.WCHAR*260)]
k.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];k.CreateToolhelp32Snapshot.restype=W.HANDLE
k.Process32FirstW.argtypes=[W.HANDLE,C.POINTER(PROCESSENTRY32W)];k.Process32NextW.argtypes=k.Process32FirstW.argtypes
k.Module32FirstW.argtypes=[W.HANDLE,C.POINTER(MODULEENTRY32W)];k.Module32NextW.argtypes=k.Module32FirstW.argtypes
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
k.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
k.CloseHandle.argtypes=[W.HANDLE]
k.WriteProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
k.VirtualAllocEx.argtypes=[W.HANDLE,C.c_void_p,C.c_size_t,W.DWORD,W.DWORD];k.VirtualAllocEx.restype=C.c_void_p
k.VirtualProtectEx.argtypes=[W.HANDLE,C.c_void_p,C.c_size_t,W.DWORD,C.POINTER(W.DWORD)]
k.FlushInstructionCache.argtypes=[W.HANDLE,C.c_void_p,C.c_size_t]
n=C.WinDLL('ntdll');n.NtSuspendProcess.argtypes=[W.HANDLE];n.NtResumeProcess.argtypes=[W.HANDLE]
def processes():
 s=k.CreateToolhelp32Snapshot(2,0); e=PROCESSENTRY32W();e.dwSize=C.sizeof(e);ok=k.Process32FirstW(s,C.byref(e));out=[]
 while ok:
  out.append((e.th32ProcessID,e.szExeFile));ok=k.Process32NextW(s,C.byref(e))
 k.CloseHandle(s);return out
def modules(pid):
 s=k.CreateToolhelp32Snapshot(0x18,pid); e=MODULEENTRY32W();e.dwSize=C.sizeof(e);ok=k.Module32FirstW(s,C.byref(e));out=[]
 while ok:
  out.append(dict(name=e.szModule,base=e.modBaseAddr,size=e.modBaseSize,path=e.szExePath));ok=k.Module32NextW(s,C.byref(e))
 k.CloseHandle(s);return out
class Mem:
 def __init__(self,pid):
  self.pid=pid;self.h=k.OpenProcess(0xC38,False,pid)
  if not self.h:raise C.WinError(C.get_last_error())
 def read(self,a,n):
  buf=C.create_string_buffer(n);got=C.c_size_t()
  if not k.ReadProcessMemory(self.h,a,buf,n,C.byref(got)) or got.value!=n:raise OSError(f'read {a:x}: {C.get_last_error()}')
  return buf.raw
 def u32(self,a):return struct.unpack('<I',self.read(a,4))[0]
 def i32(self,a):return struct.unpack('<i',self.read(a,4))[0]
 def write(self,a,data):
  data=bytes(data);buf=C.create_string_buffer(data);got=C.c_size_t();old=W.DWORD()
  if not k.VirtualProtectEx(self.h,a,len(data),0x40,C.byref(old)):raise C.WinError(C.get_last_error())
  try:
   if not k.WriteProcessMemory(self.h,a,buf,len(data),C.byref(got)) or got.value!=len(data):raise C.WinError(C.get_last_error())
   k.FlushInstructionCache(self.h,a,len(data))
  finally:k.VirtualProtectEx(self.h,a,len(data),old.value,C.byref(old))
 def put32(self,a,v):self.write(a,struct.pack('<I',v & 0xffffffff))
 def alloc(self,size):
  addr=k.VirtualAllocEx(self.h,None,size,0x3000,0x40)
  if not addr or addr>0xffffffff:raise OSError('Unable to allocate x86 memory')
  return addr
 def suspend(self):
  status=n.NtSuspendProcess(self.h)
  if status:raise OSError(f'NtSuspendProcess {status:x}')
 def resume(self):n.NtResumeProcess(self.h)
 def close(self):k.CloseHandle(self.h)
