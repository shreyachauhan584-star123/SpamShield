"""Builds data/synthetic/hindi_hinglish_synthetic_v2.csv.

SYNTHETIC: written by the project author to cover Hinglish/Hindi spelling variants, negation ("mat", "na", "न") and
fraud-awareness messages. Not real SMS. Never use as real-world evidence; the split logic keeps synthetic rows
out of validation/test whenever enough real data exists.
"""
import csv
from pathlib import Path

ROWS = [
 # ---- Hinglish: fraud / suspicious ----
 ("Apka acct block hoga. KYC update kro warna UPI band ho jayega.", "fraud"),
 ("Aapka SBI acct band hone wala hai. Turant kyc update krein: http://sbi-kyc-now.top/u", "fraud"),
 ("Aapko lottery lagi hai 15 lakh ki. Paise lene ke liye fees bhejo.", "fraud"),
 ("OTP share karo aur apna reward lo.", "fraud"),
 ("Apna otp bata do warna card block ho jayega.", "fraud"),
 ("Bijli bill bhara nahi hai. Aaj raat connection kat jayega. Is number pe call kro 9812345678", "fraud"),
 ("PAN card update nhi kiya to khata freez ho jayega. Link pe click kro http://pan-update.click/a", "fraud"),
 ("UPI refund ke liye apna pin dalo aur paisa wapas pao.", "fraud"),
 ("Loan approved! Bina document ke 2 lakh. Pehle processing fees bhejo.", "fraud"),
 ("Ghar baithe kaam karo, roz 2000 kamao. Registration fee Rs 500 bhejo.", "fraud"),
 ("Aapka parcel customs me atka hai. Delivery charge bharo: bit.ly/parcel-xx", "fraud"),
 ("Police se bol raha hu. Aapke naam par case hai. Turant paise bhejo warna arrest.", "fraud"),
 ("AnyDesk download karke code bhejo, hum aapka account theek kar denge.", "fraud"),
 ("Kisan yojana ka paisa ruka hai. Link par bank details bhejein: http://kisan-help.xyz", "fraud"),
 ("Aapka ATM pin batao warna card band.", "fraud"),
 ("Congratulations aapne iPhone jeeta hai. Claim karne ke liye link pe click karo", "fraud"),
 ("Apka aadhar block ho gya hai. Abhi update karo link se.", "fraud"),
 ("Acount band hone se bachane ke liye apna card number aur cvv bhejo.", "fraud"),
 # ---- Hinglish: legitimate / awareness / promotional ----
 ("OTP share mat karna. Aapka login code 551203 hai.", "legitimate"),
 ("Kisi ko bhi OTP na batayein. Bank kabhi OTP nahi maangta.", "legitimate"),
 ("Aapke khate se Rs 450 kat gaye. Ref no 5512093.", "legitimate"),
 ("Bijli bill jama ho gaya. Receipt number 889123.", "legitimate"),
 ("Kal subah dukaan khulegi. Saaman le aana.", "legitimate"),
 ("Doctor sahab ne kal 5 baje bulaya hai. Time par aa jana.", "legitimate"),
 ("Aapki gaadi ki service ho gayi hai. Kal le ja sakte hain.", "legitimate"),
 ("Fraud se bachein: apna PIN ya OTP kabhi kisi ko na bataye. Shak ho to bank branch jayein.", "legitimate"),
 ("Mausam kharab hai, kheti ka kaam kal karenge.", "legitimate"),
 ("Aapka recharge safal raha. Validity 28 din.", "legitimate"),
 ("Diwali offer: har kharid par 10% chhoot. Aaj hi dukaan aayein.", "promotional"),
 ("Naye mobile par exchange offer chal raha hai. Store par aayein.", "promotional"),
 # ---- Hindi (Devanagari): fraud / suspicious ----
 ("आपका बैंक अकाउंट ब्लॉक हो जाएगा। केवाईसी अपडेट करें: http://bank-kyc-up.top/x", "fraud"),
 ("आपका बैंक अकाउंट ब्लाक हो जायेगा, तुरंत केवाईसी करवाएं।", "fraud"),
 ("ओटीपी शेयर करें और इनाम पाएं।", "fraud"),
 ("आपको 10 लाख की लॉटरी लगी है। रकम पाने के लिए फीस जमा करें।", "fraud"),
 ("आपका बिजली कनेक्शन आज रात कट जाएगा। इस नंबर पर कॉल करें 9876501234", "fraud"),
 ("यूपीआई पिन डालकर अपना रिफंड प्राप्त करें।", "fraud"),
 ("पैन कार्ड अपडेट नहीं किया तो खाता बंद हो जाएगा। लिंक पर क्लिक करें।", "fraud"),
 ("लोन मंज़ूर हो गया है। बिना दस्तावेज़ के 2 लाख, पहले प्रोसेसिंग फीस जमा करें।", "fraud"),
 ("घर बैठे रोज़ 3000 कमाएँ। पंजीकरण शुल्क जमा करें।", "fraud"),
 ("आपका पार्सल कस्टम में रुका है। लिंक पर क्लिक करके शुल्क भरें।", "fraud"),
 ("सरकारी योजना की सब्सिडी रुक गई है। बैंक विवरण भेजें: http://yojana-sub.click/b", "fraud"),
 ("मैं पुलिस से बोल रहा हूँ। आपके नाम पर मामला दर्ज है। तुरंत पैसे भेजें वरना गिरफ़्तारी होगी।", "fraud"),
 ("आपका आधार बंद हो गया है। अभी लिंक से अपडेट करें।", "fraud"),
 ("अपना एटीएम पिन बताइए वरना कार्ड बंद हो जाएगा।", "fraud"),
 ("आपने आईफोन जीता है। इनाम लेने के लिए लिंक पर क्लिक करें।", "fraud"),
 # ---- Hindi: legitimate / awareness / promotional ----
 ("आपका ओटीपी 551203 है। इसे किसी को न बताएँ।", "legitimate"),
 ("किसी को भी ओटीपी या पिन न बताएँ। बैंक कभी नहीं माँगता।", "legitimate"),
 ("आपके खाते से 450 रुपये कटे हैं। संदर्भ 5512093।", "legitimate"),
 ("बिजली बिल जमा हो गया। रसीद संख्या 889123।", "legitimate"),
 ("कल दुकान जल्दी खुलेगी। सामान ले आना।", "legitimate"),
 ("डॉक्टर ने कल 5 बजे बुलाया है। समय पर आ जाना।", "legitimate"),
 ("धोखाधड़ी से बचें: अपना पिन या ओटीपी किसी को न दें।", "legitimate"),
 ("खेत की सिंचाई कल सुबह होगी। पंप चालू रखना।", "legitimate"),
 ("आपका रिचार्ज सफल रहा। वैधता 28 दिन।", "legitimate"),
 ("त्योहार पर हर ख़रीद पर 10% छूट। आज ही दुकान आएँ।", "promotional"),
 ("नए मोबाइल पर एक्सचेंज ऑफ़र चल रहा है।", "promotional"),
]

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "hindi_hinglish_synthetic_v2.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["message", "label"])
        w.writerows(ROWS)
    print(f"wrote {len(ROWS)} rows to {out}")
