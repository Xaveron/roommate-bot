## Общее

nobody = никто
language-name = { $code ->
    [ru] 🇷🇺 Русский
    [ro] 🇷🇴 Română
   *[en] 🇬🇧 English
  }
category-default-name = { $kind ->
    [bread] Хлеб
    [water] Вода
   *[trash] Мусор
  }
weekday-short = { $day ->
    [0] Пн
    [1] Вт
    [2] Ср
    [3] Чт
    [4] Пт
    [5] Сб
   *[6] Вс
  }
days-every = каждый день

## Старт и участники

start-group-created =
    👋 Привет! Я <b>RoomMate Bot</b> — помогу делить обязанности в комнате «{ $room }».

    Я веду очередь: кто покупает 🍞 хлеб, 💧 воду и выносит 🗑 мусор. В нужное время напомню тому, чья очередь, и сохраню историю.

    <b>Что сделать сейчас:</b>
    1️⃣ Каждый жилец нажимает «🏠 Я живу здесь».
    2️⃣ Каждый открывает меня в личке и нажимает «Start» — иначе я не смогу присылать личные напоминания (Telegram не разрешает ботам писать первыми).
    3️⃣ Время напоминаний и свои категории — в /settings и /add_category.

    Все команды: /help
start-group-existing =
    🏠 Комната «{ $room }» уже настроена.
    Если ты здесь живёшь — нажми кнопку ниже. И открой меня в личке, чтобы получать напоминания.
start-private-new =
    👋 Привет, { $name }!

    Теперь я смогу присылать тебе личные напоминания 🔔

    Я работаю в групповом чате вашей комнаты: добавь меня туда (кнопка ниже) и нажми /start в группе. Потом каждый жилец нажимает «🏠 Я живу здесь» и открывает меня в личке.
start-private-with-rooms =
    👋 Привет, { $name }! Личные напоминания включены 🔔

    Твои комнаты:
    { $rooms }

    Здесь, в личке, тоже работают /queue, /done и /history. Если комнат несколько — выбери активную командой /room.
btn-add-to-group = ➕ Добавить в групповой чат
btn-join = 🏠 Я живу здесь
btn-open-bot = 💬 Открыть бота в личке
join-already = Ты уже в этой комнате 🙂
join-toast = Добро пожаловать! 🎉
join-done = 🎉 { $name } теперь в комнате! Очереди обновлены.
join-done-need-dm =
    🎉 { $name } теперь в комнате! Очереди обновлены.

    ⚠️ { $name }, открой меня в личке и нажми «Start» — иначе я не смогу присылать тебе напоминания и буду писать сюда.
leave-confirm = Точно выйти из комнаты? Ты пропадёшь из всех очередей (история сохранится).
btn-leave-confirm = 🚪 Да, выйти
btn-cancel = Отмена
leave-done = 👋 { $name } больше не живёт в комнате. Очереди обновлены.
members-empty = Пока никто не отметился. Нажмите «🏠 Я живу здесь» после /start.
members-title = 👥 <b>Жильцы «{ $room }»</b> ({ $count }):
members-line = • { $name }
members-line-no-dm = • { $name } ⚠️
members-no-dm-hint = ⚠️ — я не могу писать этому жильцу в личку: нужно открыть бота и нажать «Start».
room-pick = Выбери комнату для команд в личке:
room-picked = ✅ Активная комната: { $room }
help-group =
    <b>RoomMate Bot — команды</b>

    /queue — чья сейчас очередь
    /done — отметить выполнение (в том числе вне очереди)
    /history — история по категориям
    /add_category — добавить свою категорию
    /settings — время напоминаний, тихие часы, часовой пояс, язык (для админов)
    /away — уезжаю: пропускать меня в очередях до даты
    /back — вернуться в очереди
    /members — кто живёт в комнате
    /leave — выйти из комнаты
    /cancel — отменить ввод

    Под сообщением о выполнении есть кнопки 👍 и 🤨: если большинство против, запись не засчитывается.
    Напоминания приходят в личку — открой меня и нажми «Start».
help-private =
    <b>RoomMate Bot</b>

    Сюда приходят личные напоминания. Команды для твоей комнаты:
    /queue — чья очередь
    /done — отметить выполнение
    /history — история
    /away и /back — уезжаю / вернулся домой
    /room — выбрать комнату (если их несколько)

    Настройки и новые категории — в групповом чате комнаты.

## Напоминания и кнопки

reminder-text = { $kind ->
    [bread] { $emoji } Сегодня твоя очередь купить хлеб
    [water] { $emoji } Сегодня твоя очередь купить воду
    [trash] { $emoji } Сегодня твоя очередь вынести мусор
   *[other] { $emoji } Сегодня твоя очередь: { $name }
  }
reminder-room = 🏠 { $room }
reminder-group-fallback =
    { $mention }, { $text }

    📵 Не могу написать тебе в личку — открой меня и нажми «Start», чтобы получать напоминания лично.
btn-accept = { $kind ->
    [bread] ✅ Куплю
    [water] ✅ Куплю
    [trash] ✅ Вынесу
   *[other] ✅ Сделаю
  }
btn-still-have = { $kind ->
    [bread] 🔄 Ещё есть
    [water] 🔄 Ещё есть
    [trash] 🔄 Ещё не полное
   *[other] 🔄 Пока не нужно
  }
btn-decline = ⏭ Не могу сегодня
btn-done = Готово ✅
turn-accepted = 🛒 Отлично! Нажми «Готово ✅», когда будет сделано.
turn-done = ✅ Готово, спасибо! Очередь передана дальше.
turn-snoozed = 🔄 Понял, напомню завтра.
turn-declined = ⏭ Хорошо, сегодня очередь у: { $next }. Пропуск отработаешь следующим ходом.
turn-covered = ✅ Уже сделано вне очереди: { $name }. Твоя очередь сохраняется.
toast-accepted = 👍 Жду «Готово»
toast-done = ✅ Засчитано!
toast-snoozed = 🔄 Напомню завтра
toast-declined = ⏭ Передаю очередь дальше

## Сообщения в общий чат

group-done = ✅ { $emoji } { $category } — готово! Спасибо, { $name } 🙌
group-out-of-turn = 🦸 { $emoji } { $category }: { $name } — вне очереди! Засчитано ⭐
group-next = 👉 Следующая очередь: { $name }
group-declined =
    ⏭ { $emoji } { $category }: { $name } сегодня пропускает.
    👉 Сегодня очередь: { $next }
    ⚠️ { $name } отработает пропуск следующим ходом.
group-declined-nobody =
    ⏭ { $emoji } { $category }: { $name } сегодня пропускает, а больше в очереди никого нет 🤷
    ⚠️ { $name } отработает пропуск следующим ходом.
done-pick = Что сделано? Выбери категорию:
done-not-found = Не нашёл такую категорию. Выбери из списка:
done-private-confirm = ✅ Отмечено: { $emoji } { $category }. Сообщил в общий чат.

## Очередь

queue-title = 📋 <b>Очередь — { $room }</b>
queue-nobody = 🤷 В очереди никого — нажмите «🏠 Я живу здесь»
queue-current = 👉 Сейчас: { $name } { $status ->
    [pending] — ⏳ ждём ответа
    [accepted] — 🛒 уже занимается
    [snoozed] — 🔄 ещё есть, напомню { $date }
   *[none] {""}
  }
queue-then = Дальше: { $order }
queue-legend = ⚠️ — долг за пропуск (идёт первым) · ⭐ — сделано вне очереди (следующий свой ход пропускается)

## История

history-title = 📜 <b>История — { $room }</b>
history-pick = 📜 Историю какой категории показать?
history-empty = Пока пусто.
history-col-date = Дата
history-col-who = Кто
history-col-status = Что
duty-status = { $status ->
    [done] ✅ сделано
    [skipped] ⏭ пропуск
    [still_have] 🔄 ещё есть
    [out_of_turn] 🦸 вне очереди
   *[other] { $status }
  }
btn-history-all = 📚 Все категории

## Настройки

settings-main =
    ⚙️ <b>Настройки — { $room }</b>

    🗣 Язык: { $language }
    🌍 Часовой пояс: { $timezone }
    🌙 Тихие часы: { $quiet }
    🔁 Повтор: { $repeat }
quiet-off = выключены
btn-settings-categories = ⏰ Категории и напоминания
btn-settings-quiet = 🌙 Тихие часы
btn-settings-timezone = 🌍 Часовой пояс
btn-settings-language = 🗣 Язык
btn-settings-members = 👥 Жильцы
btn-close = ✖️ Закрыть
btn-back = « Назад
btn-add-category = ➕ Добавить категорию
settings-categories =
    ⏰ <b>Категории</b>
    Выбери категорию, чтобы настроить время и дни напоминаний.
settings-category =
    { $title }

    ⏰ Время напоминания: { $time }
    📅 Дни: { $days }
    ⚖️ Очередь: { $mode }
    Состояние: { $state }
category-state = { $active ->
    [true] ✅ включена
   *[false] ⏸ отключена
  }
btn-category-time = ⏰ Время
btn-category-days = 📅 Дни
btn-category-disable = ⏸ Отключить
btn-category-enable = ▶️ Включить
btn-category-delete = 🗑 Удалить
btn-custom-time = ✍️ Своё время
btn-every-day = 📅 Каждый день
settings-delete-confirm = 🗑 Удалить категорию { $title }? Её история и очередь тоже удалятся. Если она просто временно не нужна — лучше отключи.
btn-delete-confirm = 🗑 Да, удалить
toast-category-deleted = Категория { $title } удалена
settings-quiet =
    🌙 <b>Тихие часы</b>
    В это время я не присылаю напоминания — они придут, когда тихие часы закончатся.
btn-quiet-off = 🔔 Выключить
btn-custom-range = ✍️ Свой интервал
settings-timezone =
    🌍 <b>Часовой пояс</b>
    По нему считается время напоминаний.
btn-custom-timezone = ✍️ Другой
settings-language = 🗣 <b>Язык</b> комнаты:
settings-members =
    👥 <b>Жильцы</b>
    Нажми на имя, чтобы убрать жильца из комнаты (например, после переезда).
btn-remove-member = 🚪 { $name }
settings-remove-member-confirm = Убрать { $name } из комнаты? Жилец пропадёт из всех очередей, история сохранится.
btn-remove-member-confirm = 🚪 Да, убрать
ask-time = Пришли время напоминания в формате ЧЧ:ММ, например 18:30.
ask-quiet = Пришли тихие часы в формате 23:00-08:00 (или «-», чтобы выключить).
ask-timezone = Пришли часовой пояс в формате Europe/Chisinau (список: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).
add-category-ask-name = Как назовём новую категорию? Можно сразу с эмодзи: «🧻 Туалетная бумага».
add-category-hint = 🧻 Туалетная бумага
add-category-ask-emoji = Эмодзи для «{ $name }»? Пришли один эмодзи или «-», чтобы оставить 📌.
add-category-done = ✅ Категория { $title } добавлена! Напоминание в { $time }, каждый день. Изменить — в /settings.
cancel-done = Отменено.
cancel-nothing = Нечего отменять 🙂

## Ошибки

err-generic = Что-то пошло не так 😅 Попробуй ещё раз.
err-no-room-group = Эта группа ещё не настроена — нажмите /start.
err-no-room-private = Ты пока не живёшь ни в одной комнате. Добавь меня в групповой чат комнаты, нажми там /start и «🏠 Я живу здесь».
err-not-member = Сначала отметься, что живёшь здесь 👇
err-not-admin = Настройки могут менять только админы чата и создатель комнаты.
err-assignment-closed = Эта задача уже неактуальна 🙂
err-not-your-turn = Это не твоя очередь 🙂
err-not-your-button = Эта кнопка не для тебя 🙂
err-no-categories = Активных категорий нет. Добавь: /add_category
err-category-not-found = Категория не найдена.
err-category-name = Название должно быть от 1 до { $max } символов.
err-category-emoji = Это не похоже на эмодзи. Пришли один эмодзи или «-».
err-category-exists = Категория «{ $name }» уже есть.
err-no-days = Нужен хотя бы один день.
err-bad-time = Не понял время. Пример: 18:30
err-bad-time-range = Не понял интервал. Пример: 23:00-08:00
err-bad-timezone = Не знаю такой часовой пояс. Пример: Europe/Chisinau

## Администрирование

admin-stats =
    📊 <b>Статистика бота</b>
    Комнат: { $rooms }
    Жильцов: { $members }
    Пользователей: { $users }
    Записей в истории: { $duties }
cmd-description = { $command ->
    [start] Начать / создать комнату
    [queue] Чья сейчас очередь
    [done] Отметить выполнение
    [history] История по категориям
    [add_category] Добавить категорию
    [settings] Настройки комнаты
    [members] Жильцы комнаты
    [leave] Выйти из комнаты
    [away] Уезжаю — пропускать в очередях
    [back] Вернуться в очереди
    [room] Выбрать комнату
   *[help] Помощь
  }

## Повторы напоминаний

reminder-repeat = 🔔 Напоминаю ещё раз!
nudge = { $variant ->
    [0] 👀 { $name } пока молчит про { $emoji } { $category }. Может, связь пропала? 📡
    [1] 🦗 Тишина… { $name }, { $emoji } { $category } всё ещё ждёт своего героя. Кнопки — в личке 😉
   *[2] 📣 Объявляется розыск: { $name } в последний раз видели рядом с задачей { $emoji } { $category }. Нашедшему — вечная благодарность комнаты 🙏
  }
btn-settings-repeat = 🔁 Повтор напоминаний
settings-repeat =
    🔁 <b>Повтор напоминаний</b>
    Если на напоминание нет ответа, через столько часов я напомню ещё раз, а ещё через столько же — шутливо позову в общем чате.
btn-repeat-hours = { $hours } ч
btn-repeat-off = 🔕 Не повторять
repeat-value = { $hours ->
    [0] выключен
   *[other] через { $hours } ч
  }

## Режим очереди

category-mode = { $mode ->
    [fair] справедливая (кто меньше сделал за 30 дней)
   *[round_robin] по кругу
  }
btn-category-mode = { $mode ->
    [fair] 🔄 Переключить на «по кругу»
   *[round_robin] ⚖️ Переключить на «справедливо»
  }
queue-fair = ⚖️ За 30 дней: { $counts }

## Подтверждения

btn-vote-up = 👍{ $count ->
    [0] {""}
   *[other] {" "}{ $count }
  }
btn-vote-down = 🤨 А вот и нет{ $count ->
    [0] {""}
   *[other] {" "}· { $count }
  }
toast-vote-saved = Голос учтён 👌
review-confirmed = ✅ Подтверждено большинством — { $name } молодец!
review-disputed = 🤨 Большинство против — запись не засчитана. { $name }, похоже, этот ход ещё впереди 😉
duty-disputed = { $status } 🤨
err-vote-self = За себя голосовать нельзя 🙂
err-vote-closed = Голосование уже закрыто.
err-vote-already = Твой голос уже учтён 🙂

## Отъезд

away-ask = 🏖 До какого числа тебя не будет? Пока ты в отъезде, я пропускаю тебя во всех очередях.
btn-away-days = { $days ->
    [1] Только сегодня
    [3] 3 дня
    [7] Неделю
    [14] 2 недели
   *[other] { $days } дн.
  }
btn-away-custom = ✍️ До даты…
ask-away-date = До какого числа (включительно) тебя не будет? Например: 15.10
away-set = 🏖 { $name } в отъезде до { $date } включительно — пропускаю во всех очередях. Хорошей поездки! 🚆
away-set-private = 🏖 Готово: пропускаю тебя в очередях до { $date } включительно. Вернёшься раньше — /back.
away-status = 🏖 Ты в отъезде до { $date } включительно. Уже дома? Нажми кнопку ниже.
btn-back-home = 🏠 Я уже дома
back-done = 🏠 { $name } снова дома — возвращаю в очереди, без долгов 🙂
back-done-private = 🏠 С возвращением! Ты снова в очередях, без долгов.
back-not-away = Ты и так в очередях 🙂
queue-away = 🏖 В отъезде: { $names }
queue-away-member = { $name } (до { $date })
err-bad-date = Не понял дату. Примеры: 15.10 или 15.10.2026
err-date-past = Эта дата уже прошла 🙂
err-date-too-far = Слишком далеко — максимум { $days } дней.
