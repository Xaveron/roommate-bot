## Common

nobody = nobody
language-name = { $code ->
    [ru] 🇷🇺 Русский
    [ro] 🇷🇴 Română
   *[en] 🇬🇧 English
  }
category-default-name = { $kind ->
    [bread] Bread
    [water] Water
   *[trash] Trash
  }
weekday-short = { $day ->
    [0] Mo
    [1] Tu
    [2] We
    [3] Th
    [4] Fr
    [5] Sa
   *[6] Su
  }
days-every = every day

## Start and members

start-group-created =
    👋 Hi! I'm <b>RoomMate Bot</b> and I'll help you share chores in “{ $room }”.

    I keep the queue: who buys 🍞 bread, 💧 water and takes out the 🗑 trash. At the right time I remind whoever's turn it is and keep the history.

    <b>What to do now:</b>
    1️⃣ Every roommate taps “🏠 I live here”.
    2️⃣ Everyone opens me in private chat and taps “Start” — otherwise I can't send personal reminders (Telegram doesn't let bots write first).
    3️⃣ Reminder times and custom categories — /settings and /add_category.

    All commands: /help
start-group-existing =
    🏠 The room “{ $room }” is already set up.
    If you live here, tap the button below. And open me in private chat to get reminders.
start-private-new =
    👋 Hi, { $name }!

    Now I can send you personal reminders 🔔

    I work in your room's group chat: add me there (button below) and send /start in the group. Then every roommate taps “🏠 I live here” and opens me in private chat.
start-private-with-rooms =
    👋 Hi, { $name }! Personal reminders are on 🔔

    Your rooms:
    { $rooms }

    /queue, /done and /history work here in private chat too. If you have several rooms, pick the active one with /room.
btn-add-to-group = ➕ Add to a group chat
btn-join = 🏠 I live here
btn-open-bot = 💬 Open the bot in private
join-already = You're already in this room 🙂
join-toast = Welcome! 🎉
join-done = 🎉 { $name } is now in the room! Queues updated.
join-done-need-dm =
    🎉 { $name } is now in the room! Queues updated.

    ⚠️ { $name }, open me in private chat and tap “Start” — otherwise I can't send you reminders and will have to write here.
leave-confirm = Leave the room? You'll be removed from all queues (history is kept).
btn-leave-confirm = 🚪 Yes, leave
btn-cancel = Cancel
leave-done = 👋 { $name } no longer lives in the room. Queues updated.
members-empty = Nobody has joined yet. Tap “🏠 I live here” after /start.
members-title = 👥 <b>Roommates of “{ $room }”</b> ({ $count }):
members-line = • { $name }
members-line-no-dm = • { $name } ⚠️
members-no-dm-hint = ⚠️ — I can't DM this roommate: they need to open the bot and tap “Start”.
room-pick = Pick the room for commands in private chat:
room-picked = ✅ Active room: { $room }
help-group =
    <b>RoomMate Bot — commands</b>

    /queue — whose turn it is
    /done — mark a chore as done (also out of turn)
    /history — history by category
    /add_category — add your own category
    /settings — reminder times, quiet hours, timezone, language (admins)
    /away — I'm away: skip me in queues until a date
    /back — back in the queues
    /buy salt — add to the shopping list · /list — the list · /shop — “going to the shop”
    /expense — shared expense · /balance — who owes whom
    /stats — statistics and chart · /top — leaderboard and achievements · /export — CSV
    /app — the app: tables, balance and charts
    /members — who lives in the room
    /leave — leave the room
    /cancel — cancel input

    Completion messages have 👍 and 🤨 buttons: if the majority disagrees, the record doesn't count.
    Reminders come in private chat — open me and tap “Start”.
help-private =
    <b>RoomMate Bot</b>

    Personal reminders arrive here. Commands for your room:
    /queue — whose turn it is
    /done — mark a chore as done
    /history — history
    /away and /back — leaving / back home
    /buy, /list — shopping list
    /expense, /balance — expenses and debts
    /stats, /top — statistics and leaderboard
    /app — the room app
    /room — pick a room (if you have several)

    Settings and new categories live in the room's group chat.

## Reminders and buttons

reminder-text = { $kind ->
    [bread] { $emoji } It's your turn to buy bread today
    [water] { $emoji } It's your turn to buy water today
    [trash] { $emoji } It's your turn to take out the trash today
   *[other] { $emoji } It's your turn today: { $name }
  }
reminder-room = 🏠 { $room }
reminder-group-fallback =
    { $mention }, { $text }

    📵 I can't DM you — open me and tap “Start” to get reminders privately.
btn-accept = { $kind ->
    [bread] ✅ I'll buy it
    [water] ✅ I'll buy it
    [trash] ✅ I'll take it out
   *[other] ✅ I'll do it
  }
btn-still-have = { $kind ->
    [bread] 🔄 We still have some
    [water] 🔄 We still have some
    [trash] 🔄 Not full yet
   *[other] 🔄 Not needed yet
  }
btn-decline = ⏭ Can't today
btn-done = Done ✅
turn-accepted = 🛒 Great! Tap “Done ✅” when it's done.
turn-done = ✅ Done, thanks! The turn moves on.
turn-snoozed = 🔄 Got it, I'll remind you tomorrow.
turn-declined = ⏭ OK, today it's { $next }'s turn. You'll make up for it on your next turn.
turn-covered = ✅ Already done out of turn by { $name }. You keep your turn.
toast-accepted = 👍 Waiting for “Done”
toast-done = ✅ Counted!
toast-snoozed = 🔄 I'll remind you tomorrow
toast-declined = ⏭ Passing the turn on

## Group chat messages

group-done = ✅ { $emoji } { $category } — done! Thanks, { $name } 🙌
group-out-of-turn = 🦸 { $emoji } { $category }: { $name } — out of turn! Counted ⭐
group-next = 👉 Next up: { $name }
group-declined =
    ⏭ { $emoji } { $category }: { $name } skips today.
    👉 Today's turn: { $next }
    ⚠️ { $name } will make up for it on the next turn.
group-declined-nobody =
    ⏭ { $emoji } { $category }: { $name } skips today and nobody else is in the queue 🤷
    ⚠️ { $name } will make up for it on the next turn.
done-pick = What's done? Pick a category:
done-not-found = I couldn't find that category. Pick one:
done-private-confirm = ✅ Marked: { $emoji } { $category }. I told the group chat.

## Queue

queue-title = 📋 <b>Queue — { $room }</b>
queue-nobody = 🤷 Nobody in the queue — tap “🏠 I live here”
queue-current = 👉 Now: { $name } { $status ->
    [pending] — ⏳ waiting for an answer
    [accepted] — 🛒 on it
    [snoozed] — 🔄 still have some, reminding on { $date }
   *[none] {""}
  }
queue-then = Then: { $order }
queue-legend = ⚠️ — owes a skipped turn (goes first) · ⭐ — did it out of turn (their next turn is skipped)

## History

history-title = 📜 <b>History — { $room }</b>
history-pick = 📜 Which category's history?
history-empty = Nothing yet.
history-col-date = Date
history-col-who = Who
history-col-status = What
duty-status = { $status ->
    [done] ✅ done
    [skipped] ⏭ skipped
    [still_have] 🔄 still have
    [out_of_turn] 🦸 out of turn
   *[other] { $status }
  }
btn-history-all = 📚 All categories

## Settings

settings-main =
    ⚙️ <b>Settings — { $room }</b>

    🗣 Language: { $language }
    🌍 Timezone: { $timezone }
    🌙 Quiet hours: { $quiet }
    🔁 Repeat: { $repeat }
    💱 Currency: { $currency }
    📅 Weekly summary: { $summary }
quiet-off = off
btn-settings-categories = ⏰ Categories & reminders
btn-settings-quiet = 🌙 Quiet hours
btn-settings-timezone = 🌍 Timezone
btn-settings-language = 🗣 Language
btn-settings-members = 👥 Roommates
btn-close = ✖️ Close
btn-back = « Back
btn-add-category = ➕ Add category
settings-categories =
    ⏰ <b>Categories</b>
    Pick a category to set its reminder time and days.
settings-category =
    { $title }

    ⏰ Reminder time: { $time }
    📅 Days: { $days }
    ⚖️ Queue: { $mode }
    State: { $state }
category-state = { $active ->
    [true] ✅ enabled
   *[false] ⏸ disabled
  }
btn-category-time = ⏰ Time
btn-category-days = 📅 Days
btn-category-disable = ⏸ Disable
btn-category-enable = ▶️ Enable
btn-category-delete = 🗑 Delete
btn-custom-time = ✍️ Custom time
btn-every-day = 📅 Every day
settings-delete-confirm = 🗑 Delete the category { $title }? Its history and queue will be deleted too. If you just don't need it for a while, disable it instead.
btn-delete-confirm = 🗑 Yes, delete
toast-category-deleted = Category { $title } deleted
settings-quiet =
    🌙 <b>Quiet hours</b>
    I don't send reminders during this time — they arrive when quiet hours end.
btn-quiet-off = 🔔 Turn off
btn-custom-range = ✍️ Custom range
settings-timezone =
    🌍 <b>Timezone</b>
    Reminder times are based on it.
btn-custom-timezone = ✍️ Other
settings-language = 🗣 Room <b>language</b>:
settings-members =
    👥 <b>Roommates</b>
    Tap a name to remove that roommate from the room (e.g. after moving out).
btn-remove-member = 🚪 { $name }
settings-remove-member-confirm = Remove { $name } from the room? They leave every queue, history is kept.
btn-remove-member-confirm = 🚪 Yes, remove
ask-time = Send the reminder time as HH:MM, e.g. 18:30.
ask-quiet = Send quiet hours as 23:00-08:00 (or “-” to turn them off).
ask-timezone = Send the timezone like Europe/Chisinau (list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).
add-category-ask-name = What should the new category be called? You can add an emoji: “🧻 Toilet paper”.
add-category-hint = 🧻 Toilet paper
add-category-ask-emoji = Emoji for “{ $name }”? Send one emoji or “-” to keep 📌.
add-category-done = ✅ Category { $title } added! Reminder at { $time }, every day. Change it in /settings.
cancel-done = Cancelled.
cancel-nothing = Nothing to cancel 🙂

## Errors

err-generic = Something went wrong 😅 Please try again.
err-no-room-group = This group isn't set up yet — send /start.
err-no-room-private = You don't live in any room yet. Add me to your room's group chat, send /start there and tap “🏠 I live here”.
err-not-member = First confirm that you live here 👇
err-not-admin = Only chat admins and the room creator can change settings.
err-assignment-closed = This task is no longer relevant 🙂
err-not-your-turn = It's not your turn 🙂
err-not-your-button = This button isn't for you 🙂
err-no-categories = No active categories. Add one: /add_category
err-category-not-found = Category not found.
err-category-name = The name must be 1 to { $max } characters long.
err-category-emoji = That doesn't look like an emoji. Send one emoji or “-”.
err-category-exists = Category “{ $name }” already exists.
err-no-days = At least one day is required.
err-bad-time = I didn't get the time. Example: 18:30
err-bad-time-range = I didn't get the range. Example: 23:00-08:00
err-bad-timezone = Unknown timezone. Example: Europe/Chisinau
err-turn-changed = The queue has just changed — have another look 🙂

## Administration

admin-stats =
    📊 <b>Bot statistics</b>
    Rooms: { $rooms }
    Roommates: { $members }
    Users: { $users }
    History records: { $duties }
cmd-description = { $command ->
    [start] Start / create the room
    [queue] Whose turn it is
    [done] Mark a chore as done
    [history] History by category
    [add_category] Add a category
    [settings] Room settings
    [members] Roommates
    [leave] Leave the room
    [buy] Add to the shopping list
    [list] Shopping list
    [shop] I'm going to the shop
    [expense] Add a shared expense
    [balance] Who owes whom
    [stats] Monthly statistics
    [top] Leaderboard & achievements
    [export] Export to CSV
    [away] I'm away — skip me in queues
    [back] Back in the queues
    [room] Pick a room
    [app] The room app
   *[help] Help
  }

## Repeated reminders

reminder-repeat = 🔔 Reminding you once more!
nudge = { $variant ->
    [0] 👀 { $name } is keeping quiet about { $emoji } { $category }. Lost signal, maybe? 📡
    [1] 🦗 Crickets… { $name }, { $emoji } { $category } is still waiting for its hero. The buttons are in private chat 😉
   *[2] 📣 Missing person alert: { $name } was last seen near the { $emoji } { $category } task. Reward: the eternal gratitude of the room 🙏
  }
btn-settings-repeat = 🔁 Repeat reminders
settings-repeat =
    🔁 <b>Repeat reminders</b>
    If a reminder gets no answer, I repeat it after this many hours, and after the same time again I playfully call out in the group chat.
btn-repeat-hours = { $hours } h
btn-repeat-off = 🔕 Don't repeat
repeat-value = { $hours ->
    [0] off
   *[other] after { $hours } h
  }

## Queue mode

category-mode = { $mode ->
    [fair] fair (whoever did less in 30 days)
   *[round_robin] round robin
  }
btn-category-mode = { $mode ->
    [fair] 🔄 Switch to round robin
   *[round_robin] ⚖️ Switch to fair
  }
queue-fair = ⚖️ Last 30 days: { $counts }

## Confirmations

btn-vote-up = 👍{ $count ->
    [0] {""}
   *[other] {" "}{ $count }
  }
btn-vote-down = 🤨 Nope{ $count ->
    [0] {""}
   *[other] {" "}· { $count }
  }
toast-vote-saved = Vote counted 👌
review-confirmed = ✅ Confirmed by the majority — well done, { $name }!
review-disputed = 🤨 The majority disagrees — the record doesn't count. { $name }, looks like this turn is still ahead 😉
duty-disputed = { $status } 🤨
err-vote-self = You can't vote on your own record 🙂
err-vote-closed = Voting is closed.
err-vote-already = Your vote is already counted 🙂

## Away mode

away-ask = 🏖 Until when are you away? While you're away I skip you in every queue.
btn-away-days = { $days ->
    [1] Just today
    [3] 3 days
    [7] A week
    [14] 2 weeks
   *[other] { $days } days
  }
btn-away-custom = ✍️ Until a date…
ask-away-date = Until which date (inclusive) are you away? For example: 15.10
away-set = 🏖 { $name } is away until { $date } inclusive — skipping them in every queue. Have a good trip! 🚆
away-set-private = 🏖 Done: skipping you in queues until { $date } inclusive. Back earlier? Use /back.
away-status = 🏖 You're away until { $date } inclusive. Already home? Tap the button below.
btn-back-home = 🏠 I'm back
back-done = 🏠 { $name } is back home — back in the queues, no debts (⭐ credits kept) 🙂
back-done-private = 🏠 Welcome back! You're in the queues again, no debts.
back-not-away = You're already in the queues 🙂
queue-away = 🏖 Away: { $names }
queue-away-member = { $name } (until { $date })
err-bad-date = I didn't get the date. Examples: 15.10 or 15.10.2026
err-date-past = That date has already passed 🙂
err-date-too-far = Too far away — { $days } days at most.

## Money

amount-ask = 💰 How much did it cost? Send the amount (e.g. 23.50) — I'll split it between everyone at home. Or tap “Skip”.
amount-enter = Send the amount, e.g. 23.50
amount-skipped = 👌 OK, no amount.
amount-saved = ✅ Saved: { $amount } for { $category } — split between { $count ->
    [one] { $count } person
   *[other] { $count } people
  } ({ $share } each).
amount-group = 💰 { $category }: { $name } — { $amount }. Added to /balance.
btn-amount-enter = 💰 Enter amount
btn-amount-skip = Skip
expense-ask-amount = 💸 How much was spent? E.g. 120 or 45.50
expense-ask-description = What for? E.g. “groceries for the week”. Or “-” for no description.
expense-pick =
    💸 <b>{ $amount }</b> — { $description }
    Who shares it? Tick people and tap “Save”.
btn-expense-all = 👥 Everyone
btn-expense-save = 💾 Save
expense-saved =
    💸 { $name }: <b>{ $amount }</b> — { $description }
    Split between: { $names } ({ $share } each)
toast-saved = Saved ✅
balance-title = 💰 <b>Balance — { $room }</b>
balance-empty = 🤝 All square — nobody owes anybody.
balance-line = { $name }: { $amount }
balance-transfers = <b>Who pays whom:</b>
balance-transfer = • { $debtor } → { $creditor }: { $amount }
balance-hint = Paid a debt back? Tap the matching transfer.
settle-done = 🤝 Debt settled: { $debtor } → { $creditor }, { $amount }
err-bad-amount = I didn't get the amount. Example: 23.50
err-amount-already = The amount for this record is already set.
err-expense-nobody = Pick at least one person.
err-settle-outdated = This transfer is out of date — refresh /balance.
err-settle-not-yours = Only the person who paid or the one who got the money can mark it.

## Shopping list

buy-usage = 🛒 What to buy? Example: <code>/buy salt, milk</code>
buy-added = 🛒 Added to the list: { $items }
buy-nothing-new = That's already on the list 🙂
err-buy-empty = Nothing to add — write what to buy.
err-buy-too-many = The list is too long — { $max } items at most. Tick what's bought: /list
err-item-gone = That's no longer on the list 🙂
list-title = 🛒 <b>Shopping list</b>
list-empty = Empty — add something: /buy salt
list-line = { $index }. { $item } <i>({ $name })</i>
list-hint = Bought something? Tap it below.
btn-item-bought = ✅ { $item }
btn-going-shopping = 🛒 Going to the shop
btn-refresh = 🔄 Refresh
toast-bought = Ticked ✅
shopping-going =
    🛒 { $name } is going to the shop! Need anything? Add it: /buy …

    On the list now:
    { $list }
shopping-going-dm =
    🛒 { $name } is going to the shop ({ $room }). Need anything? Write in the group chat: /buy …

    On the list:
    { $list }
shopping-going-sent = 📣 Everyone's been told!

## Statistics and achievements

month-title = { $month ->
    [1] January
    [2] February
    [3] March
    [4] April
    [5] May
    [6] June
    [7] July
    [8] August
    [9] September
    [10] October
    [11] November
   *[12] December
  } { $year }
stats-title = 📊 <b>Statistics — { $period }</b>
stats-empty = Nothing yet — a perfect time to start 🙂
stats-totals = ✅ Done: { $done } · ⏭ skipped: { $skipped } · 🤨 disputed: { $disputed }
stats-spent = 💸 Spent: { $amount }
stats-by-category = By category: { $categories }
stats-col-who = Who
stats-col-done = Done
stats-col-skipped = Skipped
stats-col-spent = Spent, { $currency }
stats-chart-title = { $period } · chores done
stats-chart-other = Other
btn-stats-prev = ◀ Previous month
btn-stats-next = Next month ▶
top-title = 🏆 <b>Leaderboard — { $period }</b>
top-empty = Nobody yet 🙂
top-line = { $place } { $name } — { $count ->
    [one] { $count } chore
   *[other] { $count } chores
  }{ $badges }
btn-achievements = 🏅 All achievements
achievements-title = 🏅 <b>Achievements</b>
achievement-line =
    { $name } — { $description }
    <i>Earned by: { $holders }</i>
achievement-name = { $code ->
    [first_duty] 🌱 First Step
    [bread_king] 👑 Bread King
    [water_carrier] 💧 Water Carrier
    [trash_ninja] 🥷 Trash Ninja
    [helper] 🦸 Superhero
    [streak_10] 🔥 No Skips
    [shopper] 🛒 Provider
    [treasurer] 💰 Treasurer
   *[centurion] 💯 Centurion
  }
achievement-description = { $code ->
    [first_duty] the first chore done
    [bread_king] bought bread 10 times
    [water_carrier] bought water 10 times
    [trash_ninja] took out the trash 10 times
    [helper] 5 chores out of turn
    [streak_10] 10 chores in a row without skipping
    [shopper] bought 10 items from the shopping list
    [treasurer] paid for 10 shared expenses
   *[centurion] 100 chores done
  }
achievement-earned = 🏆 { $name } earns “{ $achievement }” — { $description }!

## Weekly summary

summary-title = 📅 <b>Weekly summary</b> ({ $period })
summary-quiet = 😴 A quiet week — no chores marked.
summary-done = ✅ Chores done: { $count } — { $breakdown }
summary-best = 🏆 Top of the week: { $name } ({ $count })
summary-skips = ⏭ Skipped: { $skipped } · 🤨 disputed: { $disputed }
summary-spent = 💸 Spent this week: { $amount }
summary-achievements = 🏅 New achievements: { $list }
summary-footer = Have a great week! 🙌
summary-state = { $on ->
    [true] on
   *[false] off
  }
btn-settings-currency = 💱 Currency
btn-settings-summary = 📅 Weekly summary on/off
settings-currency = 💱 <b>Currency</b> for expenses and balances:

## Export

export-caption = 📦 Export of “{ $room }”: history by category and expenses (CSV, opens in Excel and Google Sheets).
export-col-date = Date
export-col-who = Who
export-col-status = Status
export-col-amount = Amount
export-col-review = Review
export-col-payer = Paid by
export-col-what = What for
export-col-type = Type
export-col-split = Owed by
export-status = { $status ->
    [done] done
    [skipped] skipped
    [still_have] still have
    [out_of_turn] out of turn
   *[other] { $status }
  }
review-status = { $status ->
    [confirmed] confirmed
    [disputed] disputed
   *[other] { $status }
  }
expense-type = { $settlement ->
    [true] debt repayment
   *[false] expense
  }
export-expenses-filename = expenses

## Mini App

btn-webapp = 📱 App
webapp-open = 📱 Queue, history, balance and statistics of “{ $room }” — in the app:
webapp-open-private = 📱 The app opens in private chat — tap the button below.
btn-webapp-private = 💬 Open in private chat
webapp-open-join = 📱 You haven't joined “{ $room }” yet. Open the app — you can join the room there.
webapp-not-configured = The app isn't connected yet.
app-away-set = 🏖 Done: skipping you in queues until { $date } inclusive.
app-category-added = ✅ Category { $title } added! Reminder at { $time }, every day.
app-left = 👋 You no longer live in “{ $room }”. The history stays.
app-member-removed = 🚪 { $name } is no longer in the room. Queues updated.
app-export-sent = 📦 Sent the CSV files to your private chat.
err-dm-needed = I can't write to you in private — open the bot, tap “Start” and try again.
