## General

nobody = nimeni
language-name = { $code ->
    [ru] 🇷🇺 Русский
    [ro] 🇷🇴 Română
   *[en] 🇬🇧 English
  }
category-default-name = { $kind ->
    [bread] Pâine
    [water] Apă
   *[trash] Gunoi
  }
weekday-short = { $day ->
    [0] Lu
    [1] Ma
    [2] Mi
    [3] Jo
    [4] Vi
    [5] Sâ
   *[6] Du
  }
days-every = în fiecare zi

## Start și locatari

start-group-created =
    👋 Salut! Sunt <b>RoomMate Bot</b> și vă ajut să împărțiți treburile în camera „{ $room }”.

    Țin evidența rândului: cine cumpără 🍞 pâine, 💧 apă și cine duce 🗑 gunoiul. La ora potrivită îi amintesc celui care e la rând și păstrez istoricul.

    <b>Ce trebuie făcut acum:</b>
    1️⃣ Fiecare coleg apasă „🏠 Locuiesc aici”.
    2️⃣ Fiecare îmi scrie în privat și apasă „Start” — altfel nu pot trimite mementouri personale (Telegram nu permite boților să scrie primii).
    3️⃣ Ora mementourilor și categoriile proprii — în /settings și /add_category.

    Toate comenzile: /help
start-group-existing =
    🏠 Camera „{ $room }” este deja configurată.
    Dacă locuiești aici, apasă butonul de mai jos. Și scrie-mi în privat ca să primești mementouri.
start-private-new =
    👋 Salut, { $name }!

    Acum îți pot trimite mementouri personale 🔔

    Funcționez în grupul camerei voastre: adaugă-mă acolo (butonul de mai jos) și apasă /start în grup. Apoi fiecare coleg apasă „🏠 Locuiesc aici” și îmi scrie în privat.
start-private-with-rooms =
    👋 Salut, { $name }! Mementourile personale sunt activate 🔔

    Camerele tale:
    { $rooms }

    Aici, în privat, funcționează și /queue, /done și /history. Dacă ai mai multe camere, alege-o pe cea activă cu /room.
btn-add-to-group = ➕ Adaugă în grup
btn-join = 🏠 Locuiesc aici
btn-open-bot = 💬 Deschide botul în privat
join-already = Ești deja în această cameră 🙂
join-toast = Bine ai venit! 🎉
join-done = 🎉 { $name } locuiește acum în cameră! Rândurile au fost actualizate.
join-done-need-dm =
    🎉 { $name } locuiește acum în cameră! Rândurile au fost actualizate.

    ⚠️ { $name }, scrie-mi în privat și apasă „Start” — altfel nu-ți pot trimite mementouri și îți voi scrie aici.
leave-confirm = Sigur vrei să ieși din cameră? Numele tău dispare din toate rândurile (istoricul rămâne).
btn-leave-confirm = 🚪 Da, ies
btn-cancel = Anulează
leave-done = 👋 { $name } nu mai locuiește în cameră. Rândurile au fost actualizate.
members-empty = Încă nu s-a înscris nimeni. Apăsați „🏠 Locuiesc aici” după /start.
members-title = 👥 <b>Locatarii „{ $room }”</b> ({ $count }):
members-line = • { $name }
members-line-no-dm = • { $name } ⚠️
members-no-dm-hint = ⚠️ — nu pot scrie în privat acestui locatar: trebuie deschis botul și apăsat „Start”.
room-pick = Alege camera pentru comenzile din privat:
room-picked = ✅ Camera activă: { $room }
help-group =
    <b>RoomMate Bot — comenzi</b>

    /queue — cine e la rând
    /done — marchează o sarcină făcută (inclusiv în afara rândului)
    /history — istoricul pe categorii
    /add_category — adaugă o categorie proprie
    /settings — ora mementourilor, ore de liniște, fus orar, limbă (pentru admini)
    /away — plec: sări-mă în rânduri până la o dată
    /back — revin în rânduri
    /buy sare — în lista de cumpărături · /list — lista · /shop — „merg la magazin”
    /expense — cheltuială comună · /balance — cine cui datorează
    /stats — statistică și grafic · /top — clasament și realizări · /export — CSV
    /members — cine locuiește în cameră
    /leave — ieși din cameră
    /cancel — anulează introducerea

    Sub mesajul despre o sarcină făcută sunt butoanele 👍 și 🤨: dacă majoritatea e împotrivă, înregistrarea nu se pune.
    Mementourile vin în privat — scrie-mi și apasă „Start”.
help-private =
    <b>RoomMate Bot</b>

    Aici primești mementouri personale. Comenzi pentru camera ta:
    /queue — cine e la rând
    /done — marchează o sarcină făcută
    /history — istoric
    /away și /back — plec / am revenit acasă
    /buy, /list — lista de cumpărături
    /expense, /balance — cheltuieli și datorii
    /stats, /top — statistică și clasament
    /room — alege camera (dacă ai mai multe)

    Setările și categoriile noi — în grupul camerei.

## Mementouri și butoane

reminder-text = { $kind ->
    [bread] { $emoji } Azi e rândul tău să cumperi pâine
    [water] { $emoji } Azi e rândul tău să cumperi apă
    [trash] { $emoji } Azi e rândul tău să duci gunoiul
   *[other] { $emoji } Azi e rândul tău: { $name }
  }
reminder-room = 🏠 { $room }
reminder-group-fallback =
    { $mention }, { $text }

    📵 Nu-ți pot scrie în privat — deschide-mă și apasă „Start” ca să primești mementouri personale.
btn-accept = { $kind ->
    [bread] ✅ Cumpăr
    [water] ✅ Cumpăr
    [trash] ✅ Îl duc
   *[other] ✅ Mă ocup
  }
btn-still-have = { $kind ->
    [bread] 🔄 Mai avem
    [water] 🔄 Mai avem
    [trash] 🔄 Nu e plin
   *[other] 🔄 Încă nu trebuie
  }
btn-decline = ⏭ Nu pot azi
btn-done = Gata ✅
turn-accepted = 🛒 Super! Apasă „Gata ✅” când e făcut.
turn-done = ✅ Gata, mulțumesc! Rândul trece mai departe.
turn-snoozed = 🔄 Am înțeles, îți amintesc mâine.
turn-declined = ⏭ Bine, azi e la rând: { $next }. Recuperezi la următoarea tură.
turn-covered = ✅ Deja făcut în afara rândului de: { $name }. Rândul tău se păstrează.
toast-accepted = 👍 Aștept „Gata”
toast-done = ✅ Înregistrat!
toast-snoozed = 🔄 Îți amintesc mâine
toast-declined = ⏭ Dau rândul mai departe

## Mesaje în grup

group-done = ✅ { $emoji } { $category } — gata! Mulțumim, { $name } 🙌
group-out-of-turn = 🦸 { $emoji } { $category }: { $name } — în afara rândului! Înregistrat ⭐
group-next = 👉 Urmează: { $name }
group-declined =
    ⏭ { $emoji } { $category }: { $name } sare peste azi.
    👉 Azi e la rând: { $next }
    ⚠️ { $name } va recupera la următoarea tură.
group-declined-nobody =
    ⏭ { $emoji } { $category }: { $name } sare peste azi și nu mai e nimeni la rând 🤷
    ⚠️ { $name } va recupera la următoarea tură.
done-pick = Ce s-a făcut? Alege categoria:
done-not-found = Nu am găsit categoria. Alege din listă:
done-private-confirm = ✅ Marcat: { $emoji } { $category }. Am anunțat în grup.

## Rândul

queue-title = 📋 <b>Rândul — { $room }</b>
queue-nobody = 🤷 Nu e nimeni la rând — apăsați „🏠 Locuiesc aici”
queue-current = 👉 Acum: { $name } { $status ->
    [pending] — ⏳ așteptăm răspuns
    [accepted] — 🛒 se ocupă deja
    [snoozed] — 🔄 mai avem, amintesc pe { $date }
   *[none] {""}
  }
queue-then = Apoi: { $order }
queue-legend = ⚠️ — are de recuperat o tură (merge primul) · ⭐ — făcut în afara rândului (următoarea tură proprie se sare)

## Istoric

history-title = 📜 <b>Istoric — { $room }</b>
history-pick = 📜 Istoricul cărei categorii?
history-empty = Deocamdată e gol.
history-col-date = Data
history-col-who = Cine
history-col-status = Ce
duty-status = { $status ->
    [done] ✅ făcut
    [skipped] ⏭ sărit
    [still_have] 🔄 mai avem
    [out_of_turn] 🦸 în afara rândului
   *[other] { $status }
  }
btn-history-all = 📚 Toate categoriile

## Setări

settings-main =
    ⚙️ <b>Setări — { $room }</b>

    🗣 Limba: { $language }
    🌍 Fus orar: { $timezone }
    🌙 Ore de liniște: { $quiet }
    🔁 Repetare: { $repeat }
    💱 Moneda: { $currency }
    📅 Rezumat săptămânal: { $summary }
quiet-off = dezactivate
btn-settings-categories = ⏰ Categorii și mementouri
btn-settings-quiet = 🌙 Ore de liniște
btn-settings-timezone = 🌍 Fus orar
btn-settings-language = 🗣 Limba
btn-settings-members = 👥 Locatari
btn-close = ✖️ Închide
btn-back = « Înapoi
btn-add-category = ➕ Adaugă categorie
settings-categories =
    ⏰ <b>Categorii</b>
    Alege o categorie ca să setezi ora și zilele mementourilor.
settings-category =
    { $title }

    ⏰ Ora mementoului: { $time }
    📅 Zile: { $days }
    ⚖️ Rând: { $mode }
    Stare: { $state }
category-state = { $active ->
    [true] ✅ activă
   *[false] ⏸ dezactivată
  }
btn-category-time = ⏰ Ora
btn-category-days = 📅 Zile
btn-category-disable = ⏸ Dezactivează
btn-category-enable = ▶️ Activează
btn-category-delete = 🗑 Șterge
btn-custom-time = ✍️ Altă oră
btn-every-day = 📅 În fiecare zi
settings-delete-confirm = 🗑 Ștergi categoria { $title }? Istoricul și rândul ei se vor șterge și ele. Dacă nu e nevoie de ea doar o vreme, mai bine dezactiveaz-o.
btn-delete-confirm = 🗑 Da, șterge
toast-category-deleted = Categoria { $title } a fost ștearsă
settings-quiet =
    🌙 <b>Ore de liniște</b>
    În acest interval nu trimit mementouri — vor veni după ce se termină orele de liniște.
btn-quiet-off = 🔔 Dezactivează
btn-custom-range = ✍️ Alt interval
settings-timezone =
    🌍 <b>Fus orar</b>
    După el se calculează ora mementourilor.
btn-custom-timezone = ✍️ Altul
settings-language = 🗣 <b>Limba</b> camerei:
settings-members =
    👥 <b>Locatari</b>
    Apasă pe un nume ca să scoți locatarul din cameră (de exemplu, după mutare).
btn-remove-member = 🚪 { $name }
settings-remove-member-confirm = Scoți pe { $name } din cameră? Dispare din toate rândurile, istoricul rămâne.
btn-remove-member-confirm = 🚪 Da, scoate
ask-time = Trimite ora mementoului în formatul HH:MM, de exemplu 18:30.
ask-quiet = Trimite orele de liniște în formatul 23:00-08:00 (sau „-” ca să le dezactivezi).
ask-timezone = Trimite fusul orar în formatul Europe/Chisinau (listă: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).
add-category-ask-name = Cum numim categoria nouă? Poți pune și un emoji: „🧻 Hârtie igienică”.
add-category-hint = 🧻 Hârtie igienică
add-category-ask-emoji = Emoji pentru „{ $name }”? Trimite un emoji sau „-” ca să rămână 📌.
add-category-done = ✅ Categoria { $title } a fost adăugată! Memento la { $time }, în fiecare zi. Se schimbă în /settings.
cancel-done = Anulat.
cancel-nothing = Nu e nimic de anulat 🙂

## Erori

err-generic = Ceva n-a mers 😅 Încearcă din nou.
err-no-room-group = Grupul încă nu e configurat — apăsați /start.
err-no-room-private = Încă nu locuiești în nicio cameră. Adaugă-mă în grupul camerei, apasă acolo /start și „🏠 Locuiesc aici”.
err-not-member = Mai întâi confirmă că locuiești aici 👇
err-not-admin = Setările le pot schimba doar adminii grupului și cel care a creat camera.
err-assignment-closed = Sarcina nu mai e actuală 🙂
err-not-your-turn = Nu e rândul tău 🙂
err-not-your-button = Butonul ăsta nu e pentru tine 🙂
err-no-categories = Nu există categorii active. Adaugă una: /add_category
err-category-not-found = Categoria nu a fost găsită.
err-category-name = Numele trebuie să aibă între 1 și { $max } caractere.
err-category-emoji = Nu pare a fi un emoji. Trimite un emoji sau „-”.
err-category-exists = Categoria „{ $name }” există deja.
err-no-days = E nevoie de cel puțin o zi.
err-bad-time = Nu am înțeles ora. Exemplu: 18:30
err-bad-time-range = Nu am înțeles intervalul. Exemplu: 23:00-08:00
err-bad-timezone = Nu cunosc acest fus orar. Exemplu: Europe/Chisinau

## Administrare

admin-stats =
    📊 <b>Statistica botului</b>
    Camere: { $rooms }
    Locatari: { $members }
    Utilizatori: { $users }
    Înregistrări în istoric: { $duties }
cmd-description = { $command ->
    [start] Pornește / creează camera
    [queue] Cine e la rând
    [done] Marchează o sarcină făcută
    [history] Istoric pe categorii
    [add_category] Adaugă o categorie
    [settings] Setările camerei
    [members] Locatarii camerei
    [leave] Ieși din cameră
    [buy] Adaugă în lista de cumpărături
    [list] Lista de cumpărături
    [shop] Merg la magazin
    [expense] Adaugă o cheltuială comună
    [balance] Cine cui datorează
    [stats] Statistica lunii
    [top] Clasament și realizări
    [export] Export CSV
    [away] Plec — sări-mă în rânduri
    [back] Revin în rânduri
    [room] Alege camera
   *[help] Ajutor
  }

## Repetarea mementourilor

reminder-repeat = 🔔 Îți amintesc încă o dată!
nudge = { $variant ->
    [0] 👀 { $name } încă tace despre { $emoji } { $category }. Poate s-a pierdut semnalul? 📡
    [1] 🦗 Liniște… { $name }, { $emoji } { $category } încă își așteaptă eroul. Butoanele sunt în privat 😉
   *[2] 📣 Căutăm pe { $name }! Ultima dată era aproape de sarcina { $emoji } { $category }. Recompensă: recunoștința veșnică a camerei 🙏
  }
btn-settings-repeat = 🔁 Repetarea mementourilor
settings-repeat =
    🔁 <b>Repetarea mementourilor</b>
    Dacă nu vine niciun răspuns, după atâtea ore amintesc încă o dată, iar după încă atâtea — chem în glumă în grup.
btn-repeat-hours = { $hours } h
btn-repeat-off = 🔕 Nu repeta
repeat-value = { $hours ->
    [0] dezactivată
   *[other] după { $hours } h
  }

## Modul rândului

category-mode = { $mode ->
    [fair] echitabil (cine a făcut mai puțin în 30 de zile)
   *[round_robin] pe rând
  }
btn-category-mode = { $mode ->
    [fair] 🔄 Treci la „pe rând”
   *[round_robin] ⚖️ Treci la „echitabil”
  }
queue-fair = ⚖️ În 30 de zile: { $counts }

## Confirmări

btn-vote-up = 👍{ $count ->
    [0] {""}
   *[other] {" "}{ $count }
  }
btn-vote-down = 🤨 Ba nu{ $count ->
    [0] {""}
   *[other] {" "}· { $count }
  }
toast-vote-saved = Vot înregistrat 👌
review-confirmed = ✅ Confirmat de majoritate — bravo, { $name }!
review-disputed = 🤨 Majoritatea e împotrivă — înregistrarea nu se pune. { $name }, se pare că tura asta mai e de făcut 😉
duty-disputed = { $status } 🤨
err-vote-self = Nu poți vota pentru tine 🙂
err-vote-closed = Votul s-a încheiat.
err-vote-already = Votul tău e deja înregistrat 🙂

## Plecare

away-ask = 🏖 Până când lipsești? Cât timp lipsești, te sar în toate rândurile.
btn-away-days = { $days ->
    [1] Doar azi
    [3] 3 zile
    [7] O săptămână
    [14] 2 săptămâni
   *[other] { $days } zile
  }
btn-away-custom = ✍️ Până la o dată…
ask-away-date = Până la ce dată (inclusiv) lipsești? De exemplu: 15.10
away-set = 🏖 { $name } lipsește până pe { $date } inclusiv — sar peste în toate rândurile. Drum bun! 🚆
away-set-private = 🏖 Gata: te sar în rânduri până pe { $date } inclusiv. Dacă revii mai devreme — /back.
away-status = 🏖 Lipsești până pe { $date } inclusiv. Ești deja acasă? Apasă butonul de mai jos.
btn-back-home = 🏠 Sunt acasă
back-done = 🏠 { $name } e din nou acasă — revine în rânduri, fără datorii (creditele ⭐ rămân) 🙂
back-done-private = 🏠 Bine ai revenit! Ești din nou în rânduri, fără datorii.
back-not-away = Ești deja în rânduri 🙂
queue-away = 🏖 Lipsesc: { $names }
queue-away-member = { $name } (până pe { $date })
err-bad-date = Nu am înțeles data. Exemple: 15.10 sau 15.10.2026
err-date-past = Data asta a trecut deja 🙂
err-date-too-far = Prea departe — maximum { $days } de zile.

## Bani

amount-ask = 💰 Cât a costat? Trimite suma (de exemplu 23.50) — o împart între toți cei care sunt acasă. Sau apasă „Sari peste”.
amount-enter = Trimite suma, de exemplu 23.50
amount-skipped = 👌 Bine, fără sumă.
amount-saved = ✅ Am notat: { $amount } pentru { $category } — împărțim la { $count ->
    [one] { $count } persoană
    [few] { $count } persoane
   *[other] { $count } de persoane
  } (câte { $share }).
amount-group = 💰 { $category }: { $name } — { $amount }. Adăugat în /balance.
btn-amount-enter = 💰 Introdu suma
btn-amount-skip = Sari peste
expense-ask-amount = 💸 Cât s-a cheltuit? De exemplu: 120 sau 45.50
expense-ask-description = Pe ce? De exemplu: „alimente pentru săptămână”. Sau „-” fără descriere.
expense-pick =
    💸 <b>{ $amount }</b> — { $description }
    Între cine împărțim? Bifează persoanele și apasă „Salvează”.
btn-expense-all = 👥 Toți
btn-expense-save = 💾 Salvează
expense-saved =
    💸 { $name }: <b>{ $amount }</b> — { $description }
    Împărțim între: { $names } (câte { $share })
toast-saved = Salvat ✅
balance-title = 💰 <b>Balanța — { $room }</b>
balance-empty = 🤝 Toți sunt chit — nimeni nu datorează nimic.
balance-line = { $name }: { $amount }
balance-transfers = <b>Cine cui transferă:</b>
balance-transfer = • { $debtor } → { $creditor }: { $amount }
balance-hint = Datoria a fost returnată? Apăsați butonul transferului.
settle-done = 🤝 Datorie închisă: { $debtor } → { $creditor }, { $amount }
err-bad-amount = Nu am înțeles suma. Exemplu: 23.50
err-amount-already = Suma pentru această înregistrare e deja introdusă.
err-expense-nobody = Alege cel puțin o persoană.
err-settle-outdated = Transferul nu mai e actual — actualizează /balance.
err-settle-not-yours = Poate marca doar cel care a transferat sau cel care a primit banii.

## Lista de cumpărături

buy-usage = 🛒 Ce trebuie cumpărat? Exemplu: <code>/buy sare, lapte</code>
buy-added = 🛒 Adăugat în listă: { $items }
buy-nothing-new = Asta e deja în listă 🙂
err-buy-empty = Nimic de adăugat — scrie ce trebuie cumpărat.
err-buy-too-many = Lista e prea lungă — maximum { $max }. Bifează ce s-a cumpărat: /list
err-item-gone = Asta nu mai e în listă 🙂
list-title = 🛒 <b>Lista de cumpărături</b>
list-empty = Goală — adaugă: /buy sare
list-line = { $index }. { $item } <i>({ $name })</i>
list-hint = Ați cumpărat? Apăsați pe produs mai jos.
btn-item-bought = ✅ { $item }
btn-going-shopping = 🛒 Merg la magazin
btn-refresh = 🔄 Actualizează
toast-bought = Bifat ✅
shopping-going =
    🛒 { $name } merge la magazin! Vă trebuie ceva? Adăugați: /buy …

    Acum în listă:
    { $list }
shopping-going-dm =
    🛒 { $name } merge la magazin ({ $room }). Îți trebuie ceva? Scrie în grup: /buy …

    În listă:
    { $list }
shopping-going-sent = 📣 I-am anunțat pe toți!

## Statistică și realizări

month-title = { $month ->
    [1] Ianuarie
    [2] Februarie
    [3] Martie
    [4] Aprilie
    [5] Mai
    [6] Iunie
    [7] Iulie
    [8] August
    [9] Septembrie
    [10] Octombrie
    [11] Noiembrie
   *[12] Decembrie
  } { $year }
stats-title = 📊 <b>Statistica — { $period }</b>
stats-empty = Deocamdată nimic — e momentul să începem 🙂
stats-totals = ✅ Făcute: { $done } · ⏭ sărite: { $skipped } · 🤨 contestate: { $disputed }
stats-spent = 💸 Cheltuit: { $amount }
stats-by-category = Pe categorii: { $categories }
stats-col-who = Cine
stats-col-done = Făcute
stats-col-skipped = Sărite
stats-col-spent = Cheltuieli, { $currency }
stats-chart-title = { $period } · sarcini făcute
stats-chart-other = Altele
btn-stats-prev = ◀ Luna trecută
btn-stats-next = Luna următoare ▶
top-title = 🏆 <b>Clasament — { $period }</b>
top-empty = Încă nimeni 🙂
top-line = { $place } { $name } — { $count ->
    [one] { $count } sarcină
    [few] { $count } sarcini
   *[other] { $count } de sarcini
  }{ $badges }
btn-achievements = 🏅 Toate realizările
achievements-title = 🏅 <b>Realizări</b>
achievement-line =
    { $name } — { $description }
    <i>Le au: { $holders }</i>
achievement-name = { $code ->
    [first_duty] 🌱 Primul pas
    [bread_king] 👑 Regele pâinii
    [water_carrier] 💧 Sacagiul
    [trash_ninja] 🥷 Ninja gunoiului
    [helper] 🦸 Supererou
    [streak_10] 🔥 Fără pauze
    [shopper] 🛒 Aprovizionatorul
    [treasurer] 💰 Trezorierul
   *[centurion] 💯 Suta
  }
achievement-description = { $code ->
    [first_duty] prima sarcină făcută
    [bread_king] de 10 ori pâine cumpărată
    [water_carrier] de 10 ori apă cumpărată
    [trash_ninja] de 10 ori gunoiul dus
    [helper] de 5 ori în afara rândului
    [streak_10] 10 sarcini la rând fără să sari
    [shopper] 10 produse cumpărate din listă
    [treasurer] 10 cheltuieli comune plătite
   *[centurion] 100 de sarcini făcute
  }
achievement-earned = 🏆 { $name } primește realizarea „{ $achievement }” — { $description }!

## Rezumatul săptămânii

summary-title = 📅 <b>Rezumatul săptămânii</b> ({ $period })
summary-quiet = 😴 Săptămână liniștită — nicio sarcină marcată.
summary-done = ✅ Sarcini făcute: { $count } — { $breakdown }
summary-best = 🏆 Pe primul loc: { $name } ({ $count })
summary-skips = ⏭ Sărite: { $skipped } · 🤨 contestate: { $disputed }
summary-spent = 💸 Cheltuit în săptămână: { $amount }
summary-achievements = 🏅 Realizări noi: { $list }
summary-footer = O săptămână bună! 🙌
summary-state = { $on ->
    [true] activat
   *[false] dezactivat
  }
btn-settings-currency = 💱 Moneda
btn-settings-summary = 📅 Rezumat săptămânal pornit/oprit
settings-currency = 💱 <b>Moneda</b> pentru cheltuieli și balanță:

## Export

export-caption = 📦 Export „{ $room }”: istoric pe categorii și cheltuieli (CSV, se deschide în Excel și Google Sheets).
export-col-date = Data
export-col-who = Cine
export-col-status = Stare
export-col-amount = Suma
export-col-review = Verificare
export-col-payer = Cine a plătit
export-col-what = Pentru ce
export-col-type = Tip
export-col-split = Cine datorează
export-status = { $status ->
    [done] făcut
    [skipped] sărit
    [still_have] mai avem
    [out_of_turn] în afara rândului
   *[other] { $status }
  }
review-status = { $status ->
    [confirmed] confirmat
    [disputed] contestat
   *[other] { $status }
  }
expense-type = { $settlement ->
    [true] returnare datorie
   *[false] cheltuială
  }
export-expenses-filename = cheltuieli
