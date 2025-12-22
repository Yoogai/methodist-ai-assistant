from aiogram.fsm.state import State, StatesGroup


class DialogStates(StatesGroup):
    main = State()
    web_search = State()
    feedback = State()
    settings = State()
    idea_mode = State()
    qr_gen_mode = State()

    # Креатив
    creative_mode = State()

    # Распознавание
    recognition_mode = State()