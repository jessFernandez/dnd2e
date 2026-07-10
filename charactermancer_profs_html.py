"""charactermancer_profs_html.py — the builder's two proficiency steps.

Split out of `charactermancer_html.py`, which had grown past two thousand lines:
Combat & Tactics turned the weapon side into weapons, mastery rungs, weapon groups,
shield/armor proficiency, fighting styles, unarmed disciplines and special talents,
and the nonweapon side gained the thief's percentage skills. `charactermancer_html`
keeps the document shell and the other steps and calls `_weapons_body` /
`_nonweapon_body` from here.

Pure string templating, Qt-free. (Not `proficiencies_html.py`, which renders the
*Codex of Worldly Craft* reference screen.)
"""
import char_rules as cr
from charactermancer import THIEF_POINT_STEP
from charactermancer_common import ABBR, budget_bar, esc

def _handedness_field(cm) -> str:
    """House-rule handedness roll (d10, 10 = ambidextrous). Rendered in the
    Proficiencies step, not Details: ambidexterity affects which weapon
    proficiencies you take (a natural 10 grants it free; otherwise warriors and
    rogues may buy it for a slot)."""
    c = cm.character
    if c.handedness_roll is None and not c.ambidextrous:
        hand = '<span class="hint">Not yet rolled.</span>'
    elif c.ambidextrous:
        why = "Ranger — automatically ambidextrous" if c.char_class == "Ranger" \
            else f"Rolled {c.handedness_roll}"
        hand = f'<span class="hand-res">Ambidextrous</span> <span class="hint">({why})</span>'
    else:
        hand = (f'<span class="hand-res">Right-handed</span> '
                f'<span class="hint">(rolled {c.handedness_roll})</span>')
    return (
        '<div class="field"><label>Handedness '
        '<span class="hint">(house rule: d10, 10 = ambidextrous)</span></label>'
        '<div class="hand-row"><a class="btn" href="dnd:///cm/handedness">🎲 Roll d10</a>'
        f'{hand}</div></div>'
    )


def _prof_meta(p) -> str:
    """The compact 'Str +0' / 'no check' meta shown on a proficiency chip."""
    if p.ability:
        return f'{ABBR.get(p.ability, p.ability)} {p.modifier:+d}'
    return "no check"


def _prof_tooltip(p) -> str:
    """A one-line hover summary of a proficiency's rules text."""
    desc = " ".join((p.description or "").split())
    return desc if len(desc) <= 280 else desc[:277].rstrip() + "…"


def _prof_description_html(p) -> str:
    """The full rules text as an expandable block (paragraphs preserved)."""
    if not p.description:
        return ""
    paras = "".join(f"<p>{esc(par)}</p>"
                    for par in p.description.split("\n\n") if par.strip())
    return (f'<details class="pr-desc"><summary>What it does</summary>'
            f'<div class="pr-desc-body">{paras}</div></details>')


def _slot_cost_label(cost: int) -> str:
    return "free" if cost == 0 else str(cost)


#: Shown under an overspent slot bar. Only a level drop can get you here.
_OVER_NOTE = ("Your level affords fewer slots than you have spent. "
              "Give some back to continue.")


def _ct_description_html(name: str) -> str:
    """An expandable "What it does" block for a Combat & Tactics style, discipline or
    talent — the same affordance the nonweapon proficiencies have.

    Shows a summary of the mechanical effect rather than the rulebook's prose (which
    spends most of its words on flavour and edge cases), then links out to the full
    rule for anyone who wants the rest."""
    summary = cr.ct_summary(name)
    if not summary:
        return ""
    page = cr.ct_page(name)
    link = (f'<p><a class="reroll" href="dnd:///newtab/{page}">'
            f'Read the full rule &rarr;</a></p>' if page else "")
    return (f'<details class="pr-desc"><summary>What it does</summary>'
            f'<div class="pr-desc-body"><p>{esc(summary)}</p>{link}</div></details>')


def _ct_tooltip(name: str) -> str:
    """A one-line hover summary for a buy-list chip."""
    summary = " ".join(cr.ct_summary(name).split())
    if not summary:
        return ""
    return esc(summary if len(summary) <= 280 else summary[:277].rstrip() + "…")


def _rung_description_html(rung: str) -> str:
    """What a weapon's mastery rung grants in play, as an expandable block with a
    link to the full Combat & Tactics rule. Empty for rungs with no write-up
    (plain proficiency, familiar)."""
    summary = cr.rung_summary(rung)
    if not summary:
        return ""
    page = cr.rung_page(rung)
    link = (f'<p><a class="reroll" href="dnd:///newtab/{page}">'
            f'Read the full rule &rarr;</a></p>' if page else "")
    return (f'<details class="pr-desc"><summary>What {cr.RUNG_LABELS[rung]} does</summary>'
            f'<div class="pr-desc-body"><p>{esc(summary)}</p>{link}</div></details>')


def _weapon_row(cm, weapon: str, rung: str, from_group: bool = False) -> str:
    """A trained weapon: its rung, the slots it costs, and the mastery steppers."""
    c = cm.character
    cost = c.weapon_prof_cost(weapon, rung)
    top = cr.next_weapon_rung(rung, c.char_class, c.level) is None

    down = (f'<a class="slot-btn" href="dnd:///cm/wpndown/{weapon}">&minus;</a>'
            if c.can_lower_weapon(weapon) else '<span class="slot-btn off">&minus;</span>')
    up = (f'<a class="slot-btn" href="dnd:///cm/wpnup/{weapon}">+</a>'
          if c.can_raise_weapon(weapon) else '<span class="slot-btn off">+</span>')

    detail = f'{cr.RUNG_LABELS[rung]} &middot; {_slot_cost_label(cost)} slot'
    detail += "s" if cost != 1 else ""
    if from_group:
        detail += ' &middot; <span class="hint">from a weapon group</span>'
    if top and cr.specialises(rung):
        detail += ' &middot; <span class="hint">top of the ladder</span>'
    # A fighter may move his specialisation here, at CT's escalating price.
    if rung == "proficient" and c.specialised_weapon() not in (None, weapon):
        respec = c.respecialisation_cost(weapon)
        if c.can_respecialise(weapon):
            detail += (f' &middot; <a class="reroll" href="dnd:///cm/respec/{weapon}">'
                       f'specialise here ({respec} slot{"s" if respec != 1 else ""})</a>')
        elif respec is not None:
            detail += (f' &middot; <span class="hint">moving specialisation here '
                       f'costs {respec} slots</span>')
    groups = cr.weapon_tight_groups(weapon)
    if groups:
        detail += f' &middot; {esc(", ".join(groups))}'

    # A group-granted proficiency has no entry of its own to remove.
    rm = ('<span class="pr-rm" title="Granted by a weapon group">•</span>' if from_group
          else f'<a class="pr-rm" href="dnd:///cm/rmweapon/{weapon}" title="Remove">✕</a>')
    return (
        '<div class="prof-row">'
        f'{rm}'
        f'<div class="pr-main"><span class="pr-name">{esc(weapon)}</span>'
        f'<span class="pr-detail">{detail}</span>{_rung_description_html(rung)}</div>'
        f'<div class="pr-slots">{down}<span class="pr-sn">{cost}</span>{up}</div>'
        '</div>')


def _weapon_group_block(cm) -> str:
    """Buy a whole tight group for 2 slots; every weapon in it becomes proficient."""
    c = cm.character
    cost = cr.WEAPON_GROUP_SLOT_COST

    bought = ""
    for group in c.weapon_groups:
        members = ", ".join(cr.weapon_group_members(group))
        rm = (f'<a class="pr-rm" href="dnd:///cm/rmgroup/{group}" title="Remove">✕</a>'
              if c.can_remove_weapon_group(group)
              else '<span class="pr-rm" title="Removing would overdraw your slots">✕</span>')
        bought += (
            '<div class="prof-row">'
            f'{rm}'
            f'<div class="pr-main"><span class="pr-name">{esc(group)}</span>'
            f'<span class="pr-detail">{esc(members)}</span></div>'
            f'<div class="pr-slots"><span class="pr-sn">{cost}</span></div></div>')

    opts = ""
    for group in cr.tight_groups_with_members():
        if group in c.weapon_groups:
            continue
        dis = "" if c.can_add_weapon_group(group) else " dis"
        tip = esc(", ".join(cr.weapon_group_members(group)))
        opts += (f'<a class="opt{dis}" href="dnd:///cm/addgroup/{group}" title="{tip}">'
                 f'<span class="opt-name">{esc(group)}</span>'
                 f'<span class="opt-cost">{cost}</span></a>')

    return (
        f'<div class="grp-label" style="margin-top:16px">Weapon groups</div>'
        f'<div class="hint">{cost} slots buys proficiency in every weapon of one tight '
        'group. Hover a group for its weapons.</div>'
        + (f'<div class="chosen-list">{bought}</div>' if bought else "")
        + f'<div class="opt-grid">{opts}</div>')


def _shield_armor_block(cm) -> str:
    """Shield and armor proficiencies — one weapon slot each."""
    c = cm.character
    rows = ""
    for name in c.shield_profs:
        detail = (f'Shield &middot; AC +{cr.shield_ac_bonus(name, True)} '
                  f'(was +{cr.shield_ac_bonus(name, False)}) &middot; blocks '
                  f'{cr.shield_attackers_blocked(name)}')
        rows += (
            '<div class="prof-row">'
            f'<a class="pr-rm" href="dnd:///cm/rmshieldprof/{name}" title="Remove">✕</a>'
            f'<div class="pr-main"><span class="pr-name">{esc(name)}</span>'
            f'<span class="pr-detail">{detail}</span></div>'
            f'<div class="pr-slots"><span class="pr-sn">{cr.SHIELD_PROF_SLOT_COST}</span>'
            '</div></div>')
    for name in c.armor_profs:
        rows += (
            '<div class="prof-row">'
            f'<a class="pr-rm" href="dnd:///cm/rmarmorprof/{name}" title="Remove">✕</a>'
            f'<div class="pr-main"><span class="pr-name">{esc(name)}</span>'
            f'<span class="pr-detail">Armor &middot; counts '
            f'{c.item_weight(name):g} lb instead of '
            f'{(cr.item(name) or {}).get("weight", 0):g}</span></div>'
            f'<div class="pr-slots"><span class="pr-sn">{cr.ARMOR_PROF_SLOT_COST}</span>'
            '</div></div>')

    opts = ""
    for name in cr.SHIELD_TYPES:
        if name in c.shield_profs:
            continue
        dis = "" if c.can_add_shield_prof(name) else " dis"
        opts += (f'<a class="opt{dis}" href="dnd:///cm/addshieldprof/{name}">'
                 f'<span class="opt-name">{esc(name)}</span>'
                 f'<span class="opt-cost">{cr.SHIELD_PROF_SLOT_COST}</span></a>')
    for name in cr.armor_items():
        if name in c.armor_profs:
            continue
        dis = "" if c.can_add_armor_prof(name) else " dis"
        opts += (f'<a class="opt{dis}" href="dnd:///cm/addarmorprof/{name}">'
                 f'<span class="opt-name">{esc(name)}</span>'
                 f'<span class="opt-cost">{cr.ARMOR_PROF_SLOT_COST}</span></a>')

    return (
        '<div class="grp-label" style="margin-top:16px">Shield &amp; armor proficiency</div>'
        '<div class="hint">One slot each. A shield proficiency raises its AC bonus and '
        'how many attackers it blocks; an armor proficiency halves that armor\'s '
        'encumbrance.</div>'
        + (f'<div class="chosen-list">{rows}</div>' if rows else "")
        + f'<div class="opt-grid">{opts}</div>')


def _fighting_styles_block(cm) -> str:
    """Warriors know every style free; nonwarriors buy one. Specialising costs a slot
    (and priests/rogues may specialise in only one style)."""
    c = cm.character
    if not c.char_class:
        return ""
    free = cr.knows_styles_free(c.char_class)

    rows = ""
    for style in cr.FIGHTING_STYLES:
        known = c.knows_style(style)
        spec = c.style_specialisation(style)
        if not known:
            continue
        cost = c.style_cost(style)
        down = (f'<a class="slot-btn" href="dnd:///cm/styledown/{style}">&minus;</a>'
                if c.can_despecialise_style(style) else '<span class="slot-btn off">&minus;</span>')
        up = (f'<a class="slot-btn" href="dnd:///cm/styleup/{style}">+</a>'
              if c.can_specialise_style(style) else '<span class="slot-btn off">+</span>')

        detail = "Known (free)" if free and spec == 0 else "Known"
        if spec:
            detail = f'Specialised &times;{spec}' if spec > 1 else "Specialised"
            if cr.style_free_specialisation(style, c.char_class):
                detail += ' &middot; <span class="hint">first slot free for rangers</span>'
        if style == "Two-Weapon":
            primary, off = c.two_weapon_penalty()
            detail += f' &middot; to-hit {primary:+d} / {off:+d}'
        rm = (f'<a class="pr-rm" href="dnd:///cm/forgetstyle/{style}" title="Unlearn">✕</a>'
              if c.can_forget_style(style) else '<span class="pr-rm">•</span>')
        rows += (
            '<div class="prof-row">'
            f'{rm}'
            f'<div class="pr-main"><span class="pr-name">{esc(style)}</span>'
            f'<span class="pr-detail">{detail}</span>{_ct_description_html(style)}</div>'
            f'<div class="pr-slots">{down}<span class="pr-sn">{cost}</span>{up}</div>'
            '</div>')

    opts = ""
    for style in cr.FIGHTING_STYLES:
        if c.knows_style(style):
            continue
        dis = "" if c.can_learn_style(style) else " dis"
        opts += (f'<a class="opt{dis}" href="dnd:///cm/learnstyle/{style}" '
                 f'title="{_ct_tooltip(style)}">'
                 f'<span class="opt-name">{esc(style)}</span>'
                 f'<span class="opt-cost">{cr.STYLE_LEARN_SLOT_COST}</span></a>')

    if free:
        note = ("Warriors know every fighting style. Specialising costs one slot, and "
                "you may specialise in as many styles as you can afford.")
    elif cr.can_specialise_styles(c.char_class):
        note = ("One slot to learn a style, one more to specialise — and a "
                f"{esc(c.char_class)} may specialise in only one style.")
    else:
        note = f"One slot to learn a style. A {esc(c.char_class)} cannot specialise in one."

    return (
        '<div class="grp-label" style="margin-top:16px">Fighting styles</div>'
        f'<div class="hint">{note}</div>'
        + (f'<div class="chosen-list">{rows}</div>' if rows else "")
        + (f'<div class="opt-grid">{opts}</div>' if opts else ""))


def _unarmed_block(cm) -> str:
    """CT Ch5 unarmed disciplines, riding the same rung ladder as weapons."""
    c = cm.character
    if not c.char_class:
        return ""

    rows = ""
    for name in cr.UNARMED_DISCIPLINES:
        entry = cr.UNARMED_DISCIPLINES[name]
        rung = c.unarmed_rung(name)
        held = name in c.unarmed_profs
        if not held and rung == "nonproficient":
            continue                       # untrained martial art: it's in the buy list
        cost = cr.unarmed_prof_cost(rung) if held else 0
        down = (f'<a class="slot-btn" href="dnd:///cm/unarmeddown/{name}">&minus;</a>'
                if c.can_lower_unarmed(name) else '<span class="slot-btn off">&minus;</span>')
        up = (f'<a class="slot-btn" href="dnd:///cm/unarmedup/{name}">+</a>'
              if c.can_raise_unarmed(name) else '<span class="slot-btn off">+</span>')
        bits = [cr.RUNG_LABELS[rung]]
        if entry.rung_cap is None:
            bits.append("cannot be advanced")
        if held and not entry.nonwarrior_benefit and \
                cr.CLASSES[c.char_class].group != "Warrior":
            bits.append("nonwarriors gain no benefit")
        if entry.note:
            bits.append(entry.note)
        rm = (f'<a class="pr-rm" href="dnd:///cm/rmunarmed/{name}" title="Remove">✕</a>'
              if held else '<span class="pr-rm" title="Free">•</span>')
        rows += (
            '<div class="prof-row">'
            f'{rm}'
            f'<div class="pr-main"><span class="pr-name">{esc(name)}</span>'
            f'<span class="pr-detail">{esc(" · ".join(bits))}</span>'
            f'{_ct_description_html(name)}</div>'
            f'<div class="pr-slots">{down}<span class="pr-sn">{cost}</span>{up}</div>'
            '</div>')

    opts = ""
    for name in cr.UNARMED_DISCIPLINES:
        if name in c.unarmed_profs or not cr.unarmed_rung_ladder(name, c.char_class, c.level):
            continue
        if not cr.is_martial_art(name) and c.unarmed_rung(name) != "familiar":
            continue
        dis = "" if c.can_add_unarmed(name) else " dis"
        opts += (f'<a class="opt{dis}" href="dnd:///cm/addunarmed/{name}" '
                 f'title="{_ct_tooltip(name)}">'
                 f'<span class="opt-name">{esc(name)}</span>'
                 f'<span class="opt-cost">{cr.unarmed_prof_cost("proficient")}</span></a>')

    return (
        '<div class="grp-label" style="margin-top:16px">Unarmed combat</div>'
        '<div class="hint">Everyone is familiar with pummeling, wrestling and '
        'overbearing for free. Proficiency costs a weapon slot; expertise is open to '
        'any class, specialisation and mastery to single-class fighters. Martial arts '
        'styles are learned separately — they form no weapon group, so they grant no '
        'familiarity, and you may be expert or specialised in only one.</div>'
        + (f'<div class="chosen-list">{rows}</div>' if rows else "")
        + (f'<div class="opt-grid">{opts}</div>' if opts else ""))


def _talent_rows(cm, names) -> str:
    c = cm.character
    rows = ""
    for name in names:
        talent = cr.TALENTS.get(name)
        if not talent:
            continue
        source = c.special_talents[name]
        bits = [f'{talent.slots} {source} slot' + ("s" if talent.slots != 1 else "")]
        skill = c.talent_skill(name)
        if skill is not None:
            bits.append(f'{ABBR.get(talent.ability, talent.ability)} check {skill}')
        # `initial_rating` is deliberately not shown: it's the Skills & Powers form of
        # the same check, and this campaign rolls the PHB one. Two numbers here would
        # only leave a player wondering which to roll against.
        rows += (
            '<div class="prof-row">'
            f'<a class="pr-rm" href="dnd:///cm/rmtalent/{name}" title="Remove">✕</a>'
            f'<div class="pr-main"><span class="pr-name">{esc(name)}</span>'
            f'<span class="pr-detail">{" &middot; ".join(bits)}</span>'
            f'{_ct_description_html(name)}</div>'
            f'<div class="pr-slots"><span class="pr-sn">{talent.slots}</span></div></div>')
    return rows


def _talent_opts(cm, talents) -> str:
    c = cm.character
    opts = ""
    for talent in talents:
        if talent.name in c.special_talents:
            continue
        dis = "" if c.can_add_talent(talent.name) else " dis"
        meta = (f'<span class="opt-meta">{ABBR.get(talent.ability, talent.ability)}</span>'
                if talent.ability else "")
        tip = _ct_tooltip(talent.name)
        opts += (f'<a class="opt{dis}" href="dnd:///cm/addtalent/{talent.name}" '
                 f'title="{tip}">'
                 f'<span class="opt-name">{esc(talent.name)}</span>{meta}'
                 f'<span class="opt-cost">{talent.slots}</span></a>')
        if talent.slot_source == "either":
            dis2 = "" if c.can_add_talent(talent.name, "nonweapon") else " dis"
            opts += (f'<a class="opt{dis2}" href="dnd:///cm/addtalentnwp/{talent.name}" '
                     f'title="Pay with a nonweapon slot instead">'
                     f'<span class="opt-name">{esc(talent.name)} (NWP)</span>'
                     f'<span class="opt-cost">{talent.slots}</span></a>')
    return opts


def _talents_block(cm) -> str:
    """CT special talents, the martial-arts talents, and the two siege proficiencies."""
    c = cm.character
    if not c.char_class:
        return ""
    chosen = set(c.special_talents)

    out = (
        '<div class="grp-label" style="margin-top:16px">Special talents</div>'
        '<div class="hint">Bought with weapon slots. Alertness and Endurance may be '
        'paid for with a nonweapon slot instead (CT marks them with an asterisk).</div>')
    rows = _talent_rows(cm, [n for n in c.special_talents if n in cr.SPECIAL_TALENTS])
    if rows:
        out += f'<div class="chosen-list">{rows}</div>'
    opts = _talent_opts(cm, cr.talents_for_class(c.char_class))
    out += (f'<div class="opt-grid">{opts}</div>' if opts else
            '<span class="hint">No talents available to this class.</span>')

    ma = cr.martial_arts_talents_for_class(c.char_class)
    if ma:
        out += '<div class="grp-label" style="margin-top:16px">Martial arts talents</div>'
        note = ('Only a martial artist can learn these. Either slot type pays.'
                if c.knows_a_martial_art() else
                'Requires proficiency in a martial arts style (see Unarmed combat above).')
        out += f'<div class="hint">{note}</div>'
        rows = _talent_rows(cm, [n for n in c.special_talents if n in cr.MARTIAL_ARTS_TALENTS])
        if rows:
            out += f'<div class="chosen-list">{rows}</div>'
        out += f'<div class="opt-grid">{_talent_opts(cm, ma)}</div>'

    siege = cr.siege_proficiencies_for_class(c.char_class)
    if siege:
        out += ('<div class="grp-label" style="margin-top:16px">Siege proficiencies</div>'
                '<div class="hint">Warfare and war-machine skills, acquired like any '
                'nonweapon proficiency — they cost a nonweapon slot.</div>')
        rows = _talent_rows(cm, [n for n in c.special_talents if n in cr.SIEGE_PROFICIENCIES])
        if rows:
            out += f'<div class="chosen-list">{rows}</div>'
        out += f'<div class="opt-grid">{_talent_opts(cm, siege)}</div>'
    return out


def _weapon_section(cm) -> str:
    c = cm.character
    total, used, left = c.weapon_slots_total(), c.weapon_slots_used(), c.weapon_slots_left()

    chosen = "".join(_weapon_row(cm, w, rung) for w, rung in c.weapon_profs.items())
    # Weapons a bought group grants: shown so they can still be specialised.
    for w in cr.WEAPONS:
        if w not in c.weapon_profs and c.group_covers(w):
            chosen += _weapon_row(cm, w, "proficient", from_group=True)
    chosen = chosen or '<span class="hint">No weapons chosen yet.</span>'

    # Ambidexterity is no longer special-cased here — it is a CT special talent and
    # lives in the talents block below.
    opts = ""
    for w in cr.WEAPONS:
        if w in c.weapon_profs or c.group_covers(w):
            continue                       # already trained, or granted by a group
        cost = c.weapon_prof_cost(w, "proficient")
        dis = "" if c.can_add_weapon(w) else " dis"
        # Flag the two things that change a weapon's price for this character.
        barred = cr.barred_weapon_penalty(w, c.char_class) if c.char_class else 0
        meta = ""
        if barred:
            meta = f'<span class="opt-meta" title="Barred to your class">+{barred}</span>'
        elif c.weapon_rung(w) == "familiar":
            meta = '<span class="opt-meta" title="Same weapon group as one you know">fam</span>'
        opts += (f'<a class="opt{dis}" href="dnd:///cm/addweapon/{w}">'
                 f'<span class="opt-name">{w}</span>{meta}'
                 f'<span class="opt-cost">{_slot_cost_label(cost)}</span></a>')

    ladder = c.weapon_rung_ladder()
    ladder_txt = " &rarr; ".join(cr.RUNG_LABELS[r] for r in ladder) if ladder else ""
    guide = (f'<div class="hint">House rules: crossbows are free, bows cost 2 slots. '
             f'Mastery ladder for a {esc(c.char_class or "character")}: {ladder_txt}. '
             'Weapons sharing a tight group make you <i>familiar</i> with the rest.'
             '</div>' if ladder else
             '<div class="hint">House rules: crossbows are free, bows cost 2 slots.</div>')

    return (
        '<section class="prof-sec">'
        '<h3 class="prof-h">Weapon Proficiencies</h3>'
        f'{_handedness_field(cm)}'
        f'{budget_bar(used, total, "Weapon slots", over_note=_OVER_NOTE)}'
        f'{guide}'
        f'<div class="chosen-list">{chosen}</div>'
        f'<div class="opt-grid">{opts}</div>'
        f'{_weapon_group_block(cm)}'
        f'{_shield_armor_block(cm)}'
        f'{_fighting_styles_block(cm)}'
        f'{_unarmed_block(cm)}'
        f'{_talents_block(cm)}'
        '</section>'
    )


def _nonweapon_section(cm) -> str:
    c = cm.character
    total, used, left = c.nonweapon_slots_total(), c.nonweapon_slots_used(), c.nonweapon_slots_left()
    known = c.nonweapon_profs

    # ── chosen ────────────────────────────────────────────────────────────────
    chosen = ""
    for name, invested in known.items():
        p = cr.NONWEAPON_PROFICIENCIES[name]
        skill = c.proficiency_skill(name)
        if skill is not None:
            detail = f'{ABBR.get(p.ability, p.ability)} &middot; check {skill} (d20+skill &ge; 21)'
        else:
            detail = "no check"
        minus = (f'<a class="slot-btn" href="dnd:///cm/profminus/{name}">&minus;</a>'
                 if invested > p.slots else '<span class="slot-btn off">&minus;</span>')
        plus = (f'<a class="slot-btn" href="dnd:///cm/profplus/{name}">+</a>'
                if left >= 1 else '<span class="slot-btn off">+</span>')
        chosen += (
            '<div class="prof-row">'
            f'<a class="pr-rm" href="dnd:///cm/rmprof/{name}" title="Remove">✕</a>'
            f'<div class="pr-main"><span class="pr-name">{esc(name)}</span>'
            f'<span class="pr-detail">{detail}</span>{_prof_description_html(p)}</div>'
            f'<div class="pr-slots">{minus}<span class="pr-sn">{invested}</span>{plus}</div>'
            '</div>'
        )
    if not chosen:
        chosen = '<span class="hint">No proficiencies chosen yet.</span>'

    # ── available: only skills this class can learn, split ready vs. locked ────
    pool = (cr.proficiencies_for_class(c.char_class) if c.char_class
            else cr.NONWEAPON_PROFICIENCIES.values())
    ready, locked = [], []
    for p in pool:
        if p.name in known:
            continue
        (ready if cr.proficiency_prereqs_met(p, known) else locked).append(p)
    ready.sort(key=lambda p: p.name)
    locked.sort(key=lambda p: p.name)

    def _chip(p, clickable: bool) -> str:
        name = f'<span class="opt-name">{esc(p.name)}</span>'
        tip = _prof_tooltip(p)
        if clickable:
            cost = f'<span class="opt-cost">{p.slots}</span>' if p.slots != 1 else ""
            meta = f'<span class="opt-meta">{_prof_meta(p)}</span>'
            dis = "" if p.slots <= left else " dis"
            return (f'<a class="opt{dis}" title="{tip}" href="dnd:///cm/addprof/{p.name}">'
                    f'{name}{meta}{cost}</a>')
        need = esc(", ".join(p.prereq))
        return (f'<span class="opt locked" title="{tip}">{name}'
                f'<span class="opt-need" title="Prerequisite">{need}</span></span>')

    avail_html = ""
    if ready:
        avail_html += ('<div class="grp-label">Available</div>'
                       f'<div class="opt-grid">{"".join(_chip(p, True) for p in ready)}</div>')
    if locked:
        avail_html += ('<div class="grp-label">Needs a prerequisite first</div>'
                       f'<div class="opt-grid">{"".join(_chip(p, False) for p in locked)}</div>')
    if not avail_html:
        avail_html = '<span class="hint">No further proficiencies available for this class.</span>'

    return (
        '<section class="prof-sec">'
        f'<h3 class="prof-h">Nonweapon Proficiencies '
        f'<span class="prof-src">from {esc(cr.PROFICIENCY_BOOK)}</span></h3>'
        f'{budget_bar(used, total, "Nonweapon slots", over_note=_OVER_NOTE)}'
        '<div class="hint">House rule: each extra slot on a proficiency adds +2 to its check. '
        'Only skills your class can learn are shown; hover a skill for its rules.</div>'
        f'<div class="chosen-list">{chosen}</div>'
        f'<div class="avail">{avail_html}</div>'
        '</section>'
    )


def _weapons_body(cm, saved=None) -> str:
    """The weapon-slot budget: weapons and their mastery rungs, weapon groups,
    shield/armor proficiency, fighting styles, unarmed disciplines and talents."""
    return f'<div class="prof-wrap">{_weapon_section(cm)}</div>'


#: The four adjustment tables are linked from the step's reference rail; only the
#: prose page that explains what each skill *does* is worth an inline link.
_THIEF_SKILLS_PAGE = "PHB/DD01505.htm"

_ARMOR_KIND_LABELS = {
    "none": "no armor",
    "leather": "leather",
    "elven_chain": "elven chain",
    "padded_studded": "padded, hide or studded leather",
    "chain_ring": "chain or ring mail",
}


def _thief_skill_breakdown(c, skill: str) -> str:
    """Where a skill's percentage came from, as a plain-text hover title."""
    dex = c.final_abilities().get("Dexterity") or 0
    parts = [f"base {cr.thief_skill_base(c.char_class, skill)}%"]
    for label, adj in (
        (str(c.race), cr.thief_racial_adjustment(c.race, skill)),
        (f"Dex {dex}", cr.thief_dex_adjustment(dex, skill)),
        (_ARMOR_KIND_LABELS[c.thief_armor_kind()], cr.thief_armor_adjustment(c.thief_armor_kind(), skill)),
    ):
        if adj:
            parts.append(f"{label} {adj:+d}%")
    spent = c.thief_points_in(skill)
    if spent:
        parts.append(f"{spent} points spent")
    return esc(", ".join(parts))


def _thief_skills_block(cm) -> str:
    """Thief/Bard only: spread the discretionary percentage points (PHB Tables 26-29)."""
    c = cm.character
    if not c.has_thief_skills():
        return ""
    total, used, left = c.thief_points_total(), c.thief_points_used(), c.thief_points_left()
    cap = cr.thief_max_points_in_skill(c.char_class, c.level)
    step = THIEF_POINT_STEP

    rows = ""
    for skill in c.thief_skill_names():
        spent = c.thief_points_in(skill)
        score = c.thief_skill_score(skill)
        capped = score >= cr.THIEF_SKILL_MAX
        minus = (f'<a class="slot-btn" href="dnd:///cm/thiefdown/{skill}">&minus;</a>'
                 if c.can_remove_thief_point(skill, step) else '<span class="slot-btn off">&minus;</span>')
        plus = (f'<a class="slot-btn" href="dnd:///cm/thiefup/{skill}">+</a>'
                if c.can_add_thief_point(skill, step) else '<span class="slot-btn off">+</span>')
        note = " &middot; at the 95% ceiling" if capped else ""
        rows += (
            '<div class="prof-row">'
            f'<div class="pr-main"><span class="pr-name">{esc(skill)}</span>'
            f'<span class="pr-detail" title="{_thief_skill_breakdown(c, skill)}">'
            f'{score}% &middot; {spent} of {cap} points{note}</span></div>'
            f'<div class="pr-slots">{minus}<span class="pr-sn">{spent}</span>{plus}</div>'
            '</div>'
        )

    armor = _ARMOR_KIND_LABELS[c.thief_armor_kind()]
    return (
        '<section class="prof-sec">'
        '<h3 class="prof-h">Thieving Skills '
        f'<span class="prof-src">PHB Tables 26&ndash;29</span></h3>'
        f'{budget_bar(used, total, "Discretionary points", unit="points spent")}'
        f'<div class="hint">Points go in blocks of {step}, at most {cap} into any one skill, '
        f'and no skill may pass {cr.THIEF_SKILL_MAX}%. Scores already include your race, '
        f'your Dexterity, and the armor you are wearing (currently {armor}) &mdash; '
        'hover a score to see the arithmetic. '
        f'<a href="dnd:///{_THIEF_SKILLS_PAGE}">What each skill does &rarr;</a>'
        '</div>'
        f'<div class="chosen-list">{rows}</div>'
        '</section>'
    )


def _nonweapon_body(cm, saved=None) -> str:
    """The nonweapon-slot budget: the campaign's skills, plus a thief's percentage skills."""
    return f'<div class="prof-wrap">{_nonweapon_section(cm)}{_thief_skills_block(cm)}</div>'

