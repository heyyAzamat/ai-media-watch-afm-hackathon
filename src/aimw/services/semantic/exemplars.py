"""Scam-phrase exemplars for the semantic matcher.

Full natural-language *phrases* (not keywords) per risk category, in Russian /
Kazakh / English — the languages AFM content appears in. The semantic matcher
embeds these once and flags spans whose meaning is close to one of them, so
paraphrases that dodge the literal lexicon in ``text_risk.py`` are still caught.

Keep these as whole phrases a scammer would actually say; the embedding model
generalises across wording, so a handful of natural seeds per category is enough.
"""

from __future__ import annotations

from ...domain.enums import RiskCategory

EXEMPLARS: dict[RiskCategory, tuple[str, ...]] = {
    RiskCategory.CASINO_ADVERTISING: (
        "play in our online casino and win big tonight",
        "claim your welcome bonus and free spins now",
        "играй в онлайн казино и выигрывай каждый день",
        "получи бонус за депозит и бесплатные вращения",
        "онлайн казинода ойнап, бонус ал",
    ),
    RiskCategory.SPORTS_BETTING: (
        "place your bet on tonight's match and win",
        "best odds on every game, bet now",
        "ставь на спорт и забирай выигрыш",
        "лучшие коэффициенты на матчи, делай ставку",
        "спортқа бәс тігіп, ұтыс ал",
    ),
    RiskCategory.ILLEGAL_GAMBLING: (
        "double your deposit and withdraw instantly",
        "stake your money and win guaranteed prizes",
        "пополни счёт и удвой свои деньги",
        "сделай ставку и гарантированно выиграй",
    ),
    RiskCategory.GUARANTEED_INCOME: (
        "earn a thousand dollars a day with no risk at all",
        "guaranteed passive income every single day",
        "зарабатывай каждый день без риска и вложений",
        "гарантированный доход, никакого риска",
        "тәуекелсіз күн сайын ақша табыңыз",
    ),
    RiskCategory.PONZI_SCHEME: (
        "your investment doubles every month, withdraw anytime",
        "guaranteed two hundred percent monthly returns",
        "вложение удваивается каждый месяц, выводи когда хочешь",
        "гарантированная прибыль двести процентов",
    ),
    RiskCategory.PYRAMID_SCHEME: (
        "build your team, recruit members and earn from their deposits",
        "join my downline and grow your network income",
        "набирай команду и зарабатывай на новых участниках",
        "пригласи людей в структуру и получай доход",
    ),
    RiskCategory.REFERRAL_SCAM: (
        "sign up using my referral link and we both get paid",
        "invite your friends with my promo code for a bonus",
        "регистрируйся по моей ссылке и получи бонус",
        "используй мой промокод, ссылка в описании",
    ),
    RiskCategory.FAKE_INVESTMENT: (
        "join my crypto trading bot for guaranteed profit",
        "my fund manager gives daily forex signals that always win",
        "инвестируй в крипту с гарантированной прибылью",
        "торговый бот приносит доход каждый день",
    ),
    RiskCategory.FINANCIAL_MANIPULATION: (
        "act now, this offer ends today, do not miss out",
        "only a few spots left, hurry before it is gone",
        "только сегодня, спеши, последний шанс",
        "не упусти момент, мест почти не осталось",
    ),
    RiskCategory.HIDDEN_ADVERTISING: (
        "this is a paid partnership, use my discount code",
        "sponsored post, affiliate link in my bio",
        "рекламная интеграция, скидка по моему промокоду",
    ),
    RiskCategory.ILLICIT_JOB_RECRUITMENT: (
        "ищем курьеров, лёгкий заработок, пиши в телеграм",
        "работа курьером, доход от трёх тысяч рублей в день, подробности в телеграме",
        "нужны люди на подработку, быстрые деньги без опыта, ссылка в телеграм",
        "требуются раскладчики, высокий доход, оптовые поставки, пиши в личку",
        "easy money courier job, high daily pay, message me on telegram",
    ),
}
