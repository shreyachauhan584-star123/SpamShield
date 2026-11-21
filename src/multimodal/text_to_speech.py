"""Browser-side speech (no server round-trip, no network for synthesis) + server-side gTTS fallback (in services/).

* `browser_tts_html`: reads text with the device's own voices (Web Speech API). If the device has NO voice for the
  language it says so; it never reads Hindi text with an English voice and never claims offline Hindi speech.
* `browser_dictation_html`: dictation helper (Web Speech API; availability and offline use depend on the browser).
  The recognised text is shown with a Copy button; the user pastes it into the message box and can edit it.
Both are rendered in Streamlit with `streamlit.components.v1.html`. Untested in a real browser in this repo.
"""
from __future__ import annotations

import html
import json

LOCALES = {"en": "en-IN", "hi": "hi-IN"}


def _js(value) -> str:
    """JSON for embedding inside <script>: '</' is escaped so user text can never close the script tag."""
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


_STYLE = ("font-family:system-ui,'Noto Sans','Noto Sans Devanagari',sans-serif;font-size:18px;padding:12px 18px;border-radius:10px;"
          "border:2px solid #12284c;background:#fff;color:#12284c;cursor:pointer;min-height:48px")


def browser_tts_html(text: str, lang: str, labels: dict) -> str:
    """labels: button, speaking, no_voice, unsupported."""
    locale = LOCALES.get(lang, "en-IN")
    return f"""<div><button id="b" style="{_STYLE}">🔊 {html.escape(labels['button'])}</button>
<div id="m" role="status" aria-live="polite" style="margin-top:8px;font-family:system-ui,sans-serif;color:#333"></div></div>
<script>
const TEXT={_js(text)}, LOCALE={_js(locale)}, L={_js({k: labels[k] for k in ('speaking', 'no_voice', 'unsupported')})};
const m=document.getElementById('m');
function pick(){{const v=window.speechSynthesis.getVoices();const l=LOCALE.toLowerCase();
  return v.find(x=>x.lang.toLowerCase().replace('_','-')===l)||v.find(x=>x.lang.toLowerCase().startsWith(l.slice(0,2)));}}
document.getElementById('b').onclick=function(){{
  if(!('speechSynthesis' in window)){{m.textContent=L.unsupported;return;}}
  const v=pick();
  if(!v&&LOCALE.startsWith('hi')){{m.textContent=L.no_voice;return;}}   // never read Devanagari with a non-Hindi voice
  window.speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(TEXT);u.lang=LOCALE;u.rate=0.9;if(v)u.voice=v;
  u.onstart=()=>m.textContent=L.speaking;u.onend=()=>m.textContent='';
  window.speechSynthesis.speak(u);}};
if('speechSynthesis' in window)window.speechSynthesis.onvoiceschanged=()=>{{}};
</script>"""


def browser_dictation_html(lang: str, labels: dict) -> str:
    """labels: start, stop, listening, unsupported, copy, copied, result_label."""
    locale = LOCALES.get(lang, "en-IN")
    return f"""<div><button id="s" style="{_STYLE}">🎤 {html.escape(labels['start'])}</button>
<div id="m" role="status" aria-live="polite" style="margin:8px 0;font-family:system-ui,sans-serif;color:#333"></div>
<textarea id="t" rows="4" style="width:100%;font-size:18px;display:none" aria-label="{html.escape(labels['result_label'])}"></textarea>
<button id="c" style="{_STYLE};display:none;margin-top:8px">📋 {html.escape(labels['copy'])}</button></div>
<script>
const LOCALE={_js(locale)}, L={_js({k: labels[k] for k in ('start', 'stop', 'listening', 'unsupported', 'copied')})};
const R=window.SpeechRecognition||window.webkitSpeechRecognition;const m=document.getElementById('m'),t=document.getElementById('t'),
 s=document.getElementById('s'),c=document.getElementById('c');let rec=null,on=false;
s.onclick=function(){{
  if(!R){{m.textContent=L.unsupported;return;}}
  if(on){{rec.stop();return;}}
  rec=new R();rec.lang=LOCALE;rec.interimResults=false;rec.continuous=false;
  rec.onstart=()=>{{on=true;s.textContent='⏹ '+L.stop;m.textContent=L.listening;}};
  rec.onend=()=>{{on=false;s.textContent='🎤 '+L.start;m.textContent='';}};
  rec.onerror=e=>{{m.textContent=String(e.error||'error');}};
  rec.onresult=e=>{{t.value=Array.from(e.results).map(r=>r[0].transcript).join(' ');t.style.display='block';c.style.display='inline-block';}};
  rec.start();}};
c.onclick=function(){{t.select();navigator.clipboard&&navigator.clipboard.writeText(t.value);m.textContent=L.copied;}};
</script>"""
