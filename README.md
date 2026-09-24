<p align="center">
  <a href="../../releases/latest/download/ukrainizer-setup.exe">
    <img alt="Завантажити українізатор" src="https://img.shields.io/badge/%D0%97%D0%B0%D0%B2%D0%B0%D0%BD%D1%82%D0%B0%D0%B6%D0%B8%D1%82%D0%B8_%D1%83%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D1%96%D0%B7%D0%B0%D1%82%D0%BE%D1%80-D3B26B?style=for-the-badge&labelColor=101216">
  </a>
</p>

<p align="center">
  <img alt="дата збірки" src="https://img.shields.io/github/release-date/pyvkules/morrowind-ukrainian-translation-public?label=%D0%B7%D1%96%D0%B1%D1%80%D0%B0%D0%BD%D0%BE&color=6A5A32&labelColor=181B21">
  <img alt="завантажень" src="https://img.shields.io/github/downloads/pyvkules/morrowind-ukrainian-translation-public/latest/total?label=%D0%B7%D0%B0%D0%B2%D0%B0%D0%BD%D1%82%D0%B0%D0%B6%D0%B5%D0%BD%D1%8C&color=6A5A32&labelColor=181B21">
</p>

<p align="center"><b>Windows</b> · нічого налаштовувати не треба</p>
# Morrowind українською

Переклад для OpenMW. Сама гра, доповнення і моди.

## Встановити

1. Забери `ukrainizer-setup.exe`.
2. Запусти.

Далі все робиться саме. Він знайде OpenMW, візьме твою копію гри і
перекладе її. Це триває хвилину або дві.

> Windows покаже «Windows protected your PC». Натисни **Докладніше**,
> а тоді **Виконати в будь-якому разі**.

Потрібен OpenMW. Гра підійде будь-яка: зі Steam, з GOG або з диска.

Щоб повернути все як було, запусти `ukrainizer-setup.exe --uninstall`.

## Скільки перекладено

Сама гра перекладена повністю. Якщо рахувати разом з модами,
українською виходить близько 72 відсотків усіх розмов.

Свіжі числа завжди є в [описі останньої збірки](../../releases/latest),
а що стоїть у черзі, видно в [PROGRESS.md](PROGRESS.md).

## Якщо щось не так

**Гра знову англійською.** Таке буває, коли відкриваєш налаштування
OpenMW і вони перескладають список тек. Просто запусти встановлювач
ще раз.

**Замість літер порожні квадратики.** Шрифтові меню бракує кирилиці.
Наприкінці встановлювач пише, з якими шрифтами він упорався. Покажи
нам цей рядок.

**Гра вилітає або щось не малюється.** Візьми `openmw.log` із теки
`Документи\My Games\OpenMW`. Якщо поруч лежить ще й `crash.log`,
додай і його.

**Будь-що інше.** [Напиши нам](../../issues/new/choose). Форма сама
спитає все потрібне, а що більше ти заповниш, то швидше знайдемо
причину.

---

Переклад і збірка живуть у цьому ж репозиторії: `tools/`, `installer/`,
`build.py`.

## Ліцензія

Український текст належить цьому проєкту. Англійський оригінал, ігрові
дані і моди належать Bethesda Softworks та авторам модів. Тут вони не
поширюються.
