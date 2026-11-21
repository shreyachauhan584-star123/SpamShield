"""Quiz items. `scam=True` means the message is suspicious. Messages are invented for teaching."""

QUIZ = [
 {"message": "Dear customer, your SBI account will be blocked today. Update KYC at http://sbi-kyc-help.top/ now.", "scam": True,
  "explanation": {"en": "Threat of blocking + hurry + a strange website ending (.top) that is not the bank's real address.", "hi": "खाता बंद करने की धमकी + जल्दबाज़ी + अजीब वेबसाइट (.top), जो बैंक का असली पता नहीं है।"}},
 {"message": "Rs 700.00 debited from A/c XX1234 on 02-Nov via UPI to Sunita Store. Ref 4412908812. If not you, call the number on your card.", "scam": False,
  "explanation": {"en": "It reports something that already happened, asks for nothing, and tells you to use the number on your own card. Still, if you did not make this payment, contact your bank.", "hi": "यह हो चुकी बात बताता है, कुछ माँगता नहीं, और आपके अपने कार्ड वाले नंबर पर फ़ोन करने को कहता है। फिर भी अगर यह भुगतान आपने नहीं किया, तो बैंक से संपर्क करें।"}},
 {"message": "Aapne 10 lakh ka inaam jeeta hai! Paane ke liye Rs 3,000 processing fee abhi bhejein.", "scam": True,
  "explanation": {"en": "A prize you never entered for, and a fee to pay first. Real prizes never work like this.", "hi": "ऐसा इनाम जिसमें आपने हिस्सा नहीं लिया, और पहले फीस भरने की माँग। असली इनाम ऐसे नहीं मिलते।"}},
 {"message": "847211 is your OTP to log in to the app. It is valid for 10 minutes. Do not share it with anyone.", "scam": False,
  "explanation": {"en": "A genuine OTP message gives a code and warns you not to share it. It is safe only if YOU just tried to log in - otherwise ignore it.", "hi": "असली OTP संदेश कोड देता है और उसे किसी को न बताने की चेतावनी देता है। यह तभी ठीक है जब आपने खुद अभी लॉगिन करने की कोशिश की हो - वरना अनदेखा करें।"}},
 {"message": "आपकी बिजली आज रात कट जाएगी। तुरंत अधिकारी को 9876500000 पर कॉल करें।", "scam": True,
  "explanation": {"en": "Electricity threat tonight + a mobile number of an 'officer'. This is a well-known scam.", "hi": "आज रात बिजली कटने की धमकी + 'अधिकारी' का मोबाइल नंबर। यह जानी-पहचानी ठगी है।"}},
 {"message": "Your cylinder booking is confirmed. Delivery within 3 days. Booking ID 55012.", "scam": False,
  "explanation": {"en": "It confirms something you did and asks you to do nothing risky.", "hi": "यह आपके किए काम की पुष्टि करता है और कोई जोखिम भरा काम करने को नहीं कहता।"}},
 {"message": "To receive your Rs 2,500 refund, enter your UPI PIN in the request you will get.", "scam": True,
  "explanation": {"en": "You never need a PIN to receive money. Entering it sends your money away.", "hi": "पैसे पाने के लिए पिन की ज़रूरत नहीं होती। पिन डालने से आपके पैसे चले जाते हैं।"}},
 {"message": "Kal subah 8 baje bus se aa raha hoon. Station par mil jana.", "scam": False,
  "explanation": {"en": "A normal personal message: no links, no money, no hurry.", "hi": "सामान्य निजी संदेश: न लिंक, न पैसे, न जल्दबाज़ी।"}},
]
