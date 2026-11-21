class _SS(dict):
    __getattr__ = dict.get
    def __setattr__(s,k,v): s[k]=v
session_state=_SS(); BUTTONS={}; CALLS=[]; UPLOAD=[None]; AUDIO=[None]
query_params={}
class _Ctx:
    def __enter__(s): return s
    def __exit__(s,*a): return False
    def __getattr__(s,n):
        import sys
        m=sys.modules[__name__]
        return globals()[n] if n in ('radio','selectbox','button','text_input','text_area','checkbox','file_uploader','toggle') else _fn
def _fn(*a, **k): CALLS.append(("fn",a[:1])); return _Ctx()
def cache_resource(*a, **k):
    if a and callable(a[0]): return a[0]
    return lambda f: f
cache_data = cache_resource
def columns(spec,**k): n = spec if isinstance(spec,int) else len(spec); return [_Ctx() for _ in range(n)]
def tabs(l): return [_Ctx() for _ in l]
def button(*a, **k):
    key=k.get('key') or a[0]
    if k.get('on_click') and BUTTONS.get(key): k['on_click'](*k.get('args',()))
    return BUTTONS.get(key, False)
def text_area(label, key=None, **k): return session_state.get(key,"")
def text_input(label, key=None, **k): return session_state.get(key,"")
def selectbox(label, options, key=None, **k):
    key=key or label; session_state.setdefault(key, options[0]); return session_state[key]
def radio(label, options, key=None, **k):
    key=key or label; session_state.setdefault(key, options[0]); return session_state[key]
def checkbox(label, value=False, key=None, **k): session_state.setdefault(key, value); return session_state[key]
def toggle(label, key=None, **k): return session_state.get(key, False)
def expander(*a, **k): return _Ctx()
def container(*a, **k): return _Ctx()
def spinner(*a, **k): return _Ctx()
class Stop(SystemExit): pass
def stop(): raise Stop()
def rerun(): pass
def file_uploader(*a, **k): return UPLOAD[0]
def audio_input(*a, **k): return AUDIO[0]
def image(*a, **k): CALLS.append(("image",))
def error(*a, **k): CALLS.append(("error", a[:1]))
def warning(*a, **k): CALLS.append(("warning", a[:1]))
def success(*a, **k): CALLS.append(("success", a[:1]))
class _SB:
    def radio(s,*a,**k): return radio(*a,**k)
    def checkbox(s,*a,**k): return checkbox(*a,**k)
    def expander(s,*a,**k): return _Ctx()
    def __getattr__(s,n): return _fn
sidebar=_SB()
def __getattr__(name): return _fn
