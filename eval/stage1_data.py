"""Hand-labeled sentences for the Stage 1 go/no-go test of Decider on the Cooloff questions.

Each row: (sentence, payment_ask, impersonation, secrecy, pressure)
  payment_ask:   none | known_bill_known_payee | gift_cards_crypto_or_wire | remote_access_request | password_or_code_request
  impersonation: none | relative_in_trouble | bank_or_fraud_dept | government | tech_support | romance | prize
  secrecy:       True when the speaker asks the listener to hide it from family or bank staff
  pressure:      0 none, 1 some urgency, 2 strong threats or demands to act now
Labels describe what the sentence says on its own, the way the gate sees it (one sentence at a time).
The set mixes scam sentences with ordinary ones, and includes hard negatives (real bills, honest family
requests, a real bank alert, a harmless secret).
"""

G, W, K, R, P, N = ("gift_cards_crypto_or_wire", "gift_cards_crypto_or_wire", "known_bill_known_payee",
                    "remote_access_request", "password_or_code_request", "none")
REL, BANK, GOV, TECH, ROM, PRIZE = ("relative_in_trouble", "bank_or_fraud_dept", "government",
                                    "tech_support", "romance", "prize")

ROWS = [
    # --- gift cards, crypto, wire
    ("Go to the pharmacy and buy four hundred dollars in Google Play gift cards, then read me the numbers.", G, N, False, 2),
    ("You need to wire the money through Western Union today and send me the tracking number.", G, N, False, 2),
    ("Put the cash into the Bitcoin machine at the gas station and scan the code I send you.", G, N, False, 2),
    ("Buy five Apple gift cards and scratch off the back so you can read me the codes.", G, N, False, 1),
    ("The only way to clear the warrant is to pay in gift cards before five o'clock.", G, GOV, False, 2),
    ("Grandma, I need you to wire two thousand dollars to this lawyer right away, I am in jail.", G, REL, True, 2),
    ("Send the fee in cryptocurrency and the prize will be released to you tonight.", G, PRIZE, False, 1),
    ("I need you to send the money by wire transfer, my bank account is frozen while I am abroad.", G, ROM, False, 1),
    ("To protect your funds, move the money into this safe account by wire transfer now.", G, BANK, False, 2),
    ("Pay the customs fee with an iTunes card and we will ship your package.", G, N, False, 1),
    # --- password, PIN, one-time code
    ("I just sent a code to your phone, please read it back to me.", P, N, False, 1),
    ("Tell me your online banking password so I can cancel the fraudulent charge.", P, BANK, False, 2),
    ("What is the PIN on your debit card? I need it to verify your identity.", P, BANK, False, 1),
    ("Please read me the six digit code that just came by text message.", P, N, False, 1),
    ("I need your Social Security number and your card PIN to stop the investigation.", P, GOV, False, 2),
    ("For the refund, confirm your account password on this call.", P, TECH, False, 1),
    ("Give me the security code on the back of your card so I can fix your account.", P, BANK, False, 1),
    ("Don't hang up, I need the verification code that was just texted to you.", P, N, False, 2),
    # --- remote access
    ("Please download this program so I can see your computer screen and fix the virus.", R, TECH, False, 1),
    ("Go to the website I give you and install the support tool, then tell me the number on the screen.", R, TECH, False, 1),
    ("Open your laptop and type the letters I read out, that lets me connect to it.", R, TECH, False, 1),
    ("I am going to take control of your computer to remove the hackers, do not turn it off.", R, TECH, False, 2),
    ("Install this app from the link so I can help you move your savings to a safe place.", R, BANK, False, 1),
    ("Share your screen with me so I can walk you through the refund.", R, N, False, 0),
    # --- ordinary known bills (not scams)
    ("This is your electric company, your usual bill of $84 is due on the 15th.", K, N, False, 0),
    ("Your water bill for September is ready, the amount is the same as last month.", K, N, False, 0),
    ("Just a reminder that your monthly insurance premium comes out of your account on Friday as usual.", K, N, False, 0),
    ("The phone company is calling to say your autopay of $45 went through today.", K, N, False, 0),
    ("Your rent is due on the first, same as always, you can pay by the usual check.", K, N, False, 0),
    ("Your gas bill was higher this month because of the cold weather, it is due next Tuesday.", K, N, False, 0),
    ("This is a reminder from your doctor's office about your twenty dollar copay at tomorrow's visit.", K, N, False, 0),
    ("Your cable bill of sixty dollars will be charged to the card on file on the twentieth.", K, N, False, 0),
    # --- relative in trouble
    ("Grandma, it's me, I'm in trouble and I need money right now.", N, REL, False, 2),
    ("Hi Grandpa, it's your grandson, I got into a car accident and I need help.", N, REL, False, 2),
    ("Mom, I lost my phone and this is a new number, can you help me with something?", N, REL, False, 1),
    ("Nana, it's me, I'm in the hospital and I can't talk long.", N, REL, False, 1),
    ("Grandpa, I've been arrested and I need bail money, please hurry.", N, REL, False, 2),
    ("Hello, this is your grandson's lawyer, he has been in an accident and needs money for the court.", N, REL, True, 2),
    ("It's your niece, I am stuck in another country and I lost my passport.", N, REL, False, 1),
    ("Grandma, guess who this is? Please don't say my name, I have a cold and my voice sounds different.", N, REL, False, 0),
    # --- bank or fraud department
    ("This is the fraud department at your bank, someone is trying to take money from your account.", N, BANK, False, 2),
    ("We have blocked your debit card because of suspicious activity, we need to verify you.", N, BANK, False, 2),
    ("Hello, I am calling from the security team at your bank about an unusual transfer.", N, BANK, False, 1),
    ("Your account has been compromised and you must act now to save your money.", N, BANK, False, 2),
    ("This is an alert from your bank, we noticed a forty dollar charge, call the number on the back of your card if it was not you.", N, BANK, False, 0),
    ("Good morning, this is the branch manager, your new debit card is ready for pickup whenever you have time.", N, BANK, False, 0),
    ("We are calling about an unusual login to your online account from another country.", N, BANK, False, 1),
    ("Our records show an unauthorized payment, please do not tell the tellers at your branch because they may be involved.", N, BANK, True, 2),
    # --- government
    ("This is the IRS, you owe back taxes and a police officer will arrive at your door within the hour.", N, GOV, False, 2),
    ("I am calling from Social Security, your number has been suspended due to criminal activity.", N, GOV, False, 2),
    ("This is Medicare, your card is about to be cancelled unless you confirm your details.", N, GOV, False, 1),
    ("There is a warrant for your arrest from the county court, you must call us back immediately.", N, GOV, False, 2),
    ("I am an agent with the immigration office and there is a problem with your records.", N, GOV, False, 1),
    ("This is the tax office confirming your appointment for Thursday at ten, please bring your documents.", N, GOV, False, 0),
    ("Hello, this is the county clerk's office, your jury duty date has changed to next month.", N, GOV, False, 0),
    ("A federal agent will call you shortly and you must not speak to anyone about this case.", N, GOV, True, 2),
    # --- tech support
    ("This is Microsoft technical support, your computer is sending out error messages and has a virus.", N, TECH, False, 1),
    ("We have detected hackers on your router and we are from your internet provider's security team.", N, TECH, False, 2),
    ("I am calling from Apple support, your iCloud account has been breached.", N, TECH, False, 1),
    ("Your computer license has expired, please stay on the line and do exactly as I say.", N, TECH, False, 2),
    ("Hi, this is Sam from the internet company, your appointment to install the new router is tomorrow between one and three.", N, TECH, False, 0),
    ("The help desk is calling back about your printer ticket, did the new cable fix it?", N, TECH, False, 0),
    # --- romance
    ("My dear, I love you more than anything, but I can't afford the ticket to come and see you.", N, ROM, False, 1),
    ("Sweetheart, I am stuck at the airport on my way to you and I need money for the customs office.", N, ROM, False, 1),
    ("Darling, you are the only person I trust, please keep our relationship secret from your children.", N, ROM, True, 1),
    ("I have never felt this way about anyone, I am a soldier overseas and I need a little help to come home to you.", N, ROM, False, 1),
    ("Honey, I made reservations at the Italian place for our anniversary dinner on Saturday.", N, N, False, 0),
    ("Dear, I miss you, can I call you again after dinner tonight?", N, N, False, 0),
    # --- prize or lottery
    ("Congratulations, you have won the national lottery, one million dollars is waiting for you.", N, PRIZE, False, 1),
    ("You are the lucky winner of a free cruise, we only need a small processing fee to confirm.", N, PRIZE, False, 1),
    ("This is the sweepstakes office, you have won a new car but you must claim it today or lose it.", N, PRIZE, False, 2),
    ("You were selected for a cash prize, do not tell anyone until we finish the paperwork.", N, PRIZE, True, 1),
    ("Thank you for entering our store draw, the winner will be announced next Friday on our website.", N, N, False, 0),
    ("Your library raffle ticket number twelve won a basket of books, pick it up any day this week.", N, PRIZE, False, 0),
    # --- secrecy, scam
    ("Please don't tell anyone at the bank why you are taking out the money, they will just get in the way.", N, N, True, 1),
    ("Don't tell your parents about this, they will only make it worse.", N, N, True, 1),
    ("If the teller asks, say the cash is for a home repair and nothing else.", N, N, True, 1),
    ("This is just between you and me, do not mention it to your son or your daughter.", N, N, True, 1),
    ("You must not discuss this call with your family, it is a matter of national security.", N, GOV, True, 2),
    ("Keep this a secret, if you tell anyone the deal is off.", N, N, True, 2),
    # --- ordinary sentences and hard negatives
    ("Your pharmacy order is ready for pickup after three o'clock.", N, N, False, 0),
    ("Hi Grandma, it's Emma, I'll be home from college on Friday, can you make your lasagna?", N, N, False, 0),
    ("Hello, this is Dr. Patel's office, we need to move your appointment from Tuesday to Wednesday.", N, N, False, 0),
    ("Mom, can you lend me twenty dollars until Friday for lunch? I will pay you back.", N, N, False, 0),
    ("Grandpa, the bus fare for the school trip is fifteen dollars, can you give it to me tomorrow?", N, N, False, 0),
    ("We are planning a surprise party for Dad, please keep it between us until Saturday.", N, N, True, 0),
    ("It's Tom from next door, your delivery was left at my place, I will bring it over now.", N, N, False, 0),
    ("Good afternoon, we are calling from the grocery store, your order of apples and bread is on its way.", N, N, False, 0),
    ("Are you free for coffee on Thursday? The usual place at ten works for me.", N, N, False, 0),
    ("Your prescription refill is ready, there is no payment needed because it is covered by your plan.", N, N, False, 0),
    ("The church bake sale is on Sunday, would you like to bring a pie?", N, N, False, 0),
    ("This is your daughter, I am at the airport, my flight just landed and I will take a taxi home.", N, N, False, 0),
    ("Hi, I'm calling about the car you have for sale, is it still available?", N, N, False, 0),
    ("Your appointment at the dentist is confirmed for Monday at two.", N, N, False, 0),
    ("I am calling to remind you that your library books are due on Friday.", N, N, False, 0),
    ("Please call me back when you get this message, nothing urgent.", N, N, False, 0),
    ("Mom, I'm okay, just a small fender bender but the car is fine and nobody was hurt.", N, N, False, 0),
    ("The bank branch will be closed on Monday for the holiday, please plan ahead.", N, BANK, False, 0),
    ("Hello Mr. Rao, this is Priya from the credit union, your savings statement is ready to pick up at the front desk.", N, BANK, False, 0),
    ("Your grandson asked me to give you a call, he said he will visit on Sunday afternoon.", N, N, False, 0),
]
