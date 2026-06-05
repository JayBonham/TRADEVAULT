# =============================================================================
# YOUR FUNNEL — edit everything in this file. Don't touch bot.py.
#
# This mirrors the *structure* of a typical onboarding funnel:
#   welcome -> video -> capture name -> capture email -> pitch
#   -> branching button menus -> next-steps -> wrap-up
#
# Step types:
#   message     {text, delay?}                       auto-sent text
#   photo       {file, caption?, delay?}             image from ./media/
#   video_note  {file, delay?}                       round video from ./media/
#   input       {prompt, save_as, validate?, delay?} stop & capture a typed reply
#   buttons     {text, options:[{label, goto}]}      inline menu that branches
#   goto        {target}                             jump to another step id
#
# - Every step needs a unique "id".
# - Use {placeholders} in any text to drop in captured values, e.g. {full_name}.
# - validate currently supports "email".
#
# NOTE: the words below are neutral placeholders. Whatever offer you drop in,
# you're responsible for the claims being truthful and the signup path being the
# properly regulated one — that's the part that keeps you out of trouble.
# =============================================================================

FLOW = [
    # --- intro -------------------------------------------------------------
    {
        "id": "welcome",
        "type": "message",
        "text": "Welcome! Great to have you here. 👋",
        "delay": 1.0,
    },
    # --- lead capture ------------------------------------------------------
    {
        "id": "ask_name",
        "type": "input",
        "prompt": "Let me know your full name below please.",
        "save_as": "full_name",
        "delay": 0.8,
    },
    {
        "id": "greet_name",
        "type": "message",
        "text": "Thanks {full_name}!",
        "delay": 0.8,
    },
    {
        "id": "ask_email",
        "type": "input",
        "prompt": "Great — please enter your email for access.",
        "save_as": "email",
        "validate": "email",
        "delay": 0.6,
    },

    # --- pitch -------------------------------------------------------------
    {
        "id": "rundown",
        "type": "message",
        "text": (
            "Here's a quick rundown of what's inside:\n\n"
            "• [benefit one]\n"
            "• [benefit two]\n"
            "• [benefit three]"
        ),
        "delay": 1.0,
    },
    # --- first branching menu ---------------------------------------------
    {
        "id": "menu_main",
        "type": "buttons",
        "text": "Ready when you are 👇",
        "options": [
            {"label": "Next Steps", "goto": "next_steps"},
            {"label": "How does it work?", "goto": "how_it_works"},
        ],
        "delay": 0.6,
    },

    # branch: "How does it work?" -> explain, then loop back to the menu
    {
        "id": "how_it_works",
        "type": "message",
        "text": "[Explain how your program works here.]",
        "delay": 0.8,
    },
    {"id": "back_to_menu", "type": "goto", "target": "menu_main"},

    # branch: "Next Steps" -> second menu
    {
        "id": "next_steps",
        "type": "message",
        "text": "Awesome — let's get you set up.",
        "delay": 0.8,
    },
    {
        "id": "ask_experience",
        "type": "buttons",
        "text": "Have you done anything like this before?",
        "options": [
            {"label": "Yes 💪", "goto": "has_experience"},
            {"label": "No, I'm new", "goto": "is_new"},
        ],
        "delay": 0.6,
    },

    # branch: experienced -> straight to wrap-up
    {
        "id": "has_experience",
        "type": "message",
        "text": "Perfect, you'll feel right at home.",
        "delay": 0.8,
    },
    {"id": "skip_to_wrap", "type": "goto", "target": "wrap_up"},

    # branch: new -> extra guidance, then wrap-up
    {
        "id": "is_new",
        "type": "message",
        "text": "No problem at all — here's how to get started.\n\n[Setup guidance.]",
        "delay": 0.8,
    },

    # --- end ---------------------------------------------------------------
    {
        "id": "wrap_up",
        "type": "message",
        "text": "You're all set, {full_name}. A team member will follow up shortly. 🚀",
        "delay": 1.0,
    },
]
