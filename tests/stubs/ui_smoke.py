import os, sys, runpy, time, tempfile
os.environ["GRAMSURAKSHA_DB_PATH"]=tempfile.mkdtemp()+"/f.db"; os.environ["GRAMSURAKSHA_TTS"]="none"
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0,HERE); sys.path.insert(0,ROOT); os.chdir(ROOT)
import streamlit as st
from streamlit.components import v1
from tests.helpers import make_sms_screenshot
class Up:
    def __init__(s,b): s._b=b
    def getvalue(s): return s._b
def run(path, expect_exit=False, **state):
    st.session_state.clear(); st.session_state.update(state); st.CALLS.clear()
    try: runpy.run_path(path, run_name="__main__")
    except st.Stop:
        if not expect_exit: raise
        print("STOPPED (guard)", path); return
    print("OK", path, "| user-visible errors:", [c[1][0][:40] for c in st.CALLS if c[0]=="error" and "must never" not in str(c[1])])
for lang in ("en","hi"):
    run('app.py', ui_lang=lang)
    # paste -> analyze
    st.BUTTONS.clear(); st.BUTTONS["go_paste"]=True
    run('pages/1_Analyze_SMS.py', ui_lang=lang, sms_input="Your account will be blocked. Update KYC immediately: http://sbi-kyc-update.xyz/login", msg_lang="auto")
    assert st.session_state.get("result") and st.session_state["result"]["risk"]["level"]=="HIGH"
    # result views for every level + feedback + contribution
    from src.services.analysis_service import analyze_sms
    for text in ["Your account will be blocked. Update KYC immediately: http://sbi-kyc-update.xyz/login","Kal subah dukaan khulegi saaman le aana","ok","Aapka acct block hoga kyc update kro"]:
        res=analyze_sms(text); lvl=res["risk"]["level"]
        st.BUTTONS.clear(); st.BUTTONS.update({"fb_correct_fraud":True,"fb_correct_legitimate":True,"fb_ey":True,"contrib_btn":True,"listen":True})
        run('pages/1_Analyze_SMS.py', ui_lang=lang, result=res, fb_consent=True, contrib_consent=True, fb_comment="useful, call 9876543210")
        print("  level",lvl,"fb_done",st.session_state.get("fb_done"),"contrib",bool(st.session_state.get("contrib_done")))
    # another message button
    st.BUTTONS.clear(); st.BUTTONS["Check another message"]=True
    # screenshot -> OCR -> edit -> analyze
    st.UPLOAD[0]=Up(make_sms_screenshot(["Your account will be blocked today.","Update your KYC immediately:","http://sbi-kyc-update.xyz/login"]))
    st.BUTTONS.clear(); st.BUTTONS["read_img"]=True; st.BUTTONS["go_ocr"]=True
    run('pages/1_Analyze_SMS.py', ui_lang=lang, msg_lang="auto")
    print("  ocr text:", repr(st.session_state.get("ocr_text"))[:80])
    st.UPLOAD[0]=Up(b"not an image"); st.BUTTONS.clear(); st.BUTTONS["read_img"]=True
    run('pages/1_Analyze_SMS.py', ui_lang=lang); st.UPLOAD[0]=None
    # education / about
    for qs in ({}, {"quiz_i":3,"quiz_answer":True}, {"quiz_i":8,"quiz_score":4}):
        run('pages/2_Fraud_Awareness.py', ui_lang=lang, **qs)
    st.BUTTONS.clear(); st.BUTTONS["del_btn"]=True
    run('pages/4_About.py', ui_lang=lang, del_token="nope")
# guards
for pth in ('pages/3_Model_Insights.py','pages/5_Staff.py'):
    run(pth, expect_exit=True, ui_lang="en")
run('pages/3_Model_Insights.py', ui_lang="en", is_admin=True, admin_since=time.time())
st.BUTTONS.clear()
run('pages/5_Staff.py', ui_lang="en", is_admin=True, admin_since=time.time(), reviewer_name="Asha")
run('pages/5_Staff.py', expect_exit=True, ui_lang="en", is_admin=True, admin_since=time.time()-4000)   # expired session
import sqlite3
con=sqlite3.connect(os.environ["GRAMSURAKSHA_DB_PATH"])
cols=[r[1] for t in ("feedback","audit_log") for r in con.execute(f"PRAGMA table_info({t})")]
n_fb=con.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]; n_c=con.execute("SELECT COUNT(*) FROM contributions").fetchone()[0]
stored=" ".join(r[0] for r in con.execute("SELECT message_text FROM contributions"))
assert n_fb>0 and n_c>0, (n_fb,n_c)
assert not [c for c in cols if c in ("message","message_text","text","sms","body","url")]
assert "9876543210" not in str(con.execute("SELECT comment FROM feedback").fetchall()), "comment not redacted"
print("SMOKE_OK", "feedback_rows", n_fb, "contributions", n_c, "tts_snippets", len(v1.HTML))
