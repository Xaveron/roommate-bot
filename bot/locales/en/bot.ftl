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
    /members — who lives in the room
    /leave — leave the room
    /cancel — cancel input

    Reminders come in private chat — open me and tap “Start”.
help-private =
    <b>RoomMate Bot</b>

    Personal reminders arrive here. Commands for your room:
    /queue — whose turn it is
    /done — mark a chore as done
    /history — history
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
    [room] Pick a room
   *[help] Help
  }
