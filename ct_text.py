"""ct_text.py — Combat & Tactics rules prose. GENERATED, DO NOT EDIT.

Regenerate with:  python scripts/build_ct_text.py

Maps a fighting style / unarmed discipline / talent to the page it comes
from and its rules text, so the builder can show a "What it does" block
without char_rules reaching into the database.
"""

CT_TEXT = {
    'Alertness': {
        "page": 'CT/DD02654.htm',
        "description": 'Some characters are unnaturally alert and instinctively note signs of trouble that other characters may miss. A character with this proficiency reduces his chance of being surprised by 1 in 10 if he makes a successful proficiency check. In situations where surprise is automatic, the character may still attempt a proficiency check. If he passes, he is surprised at the normal chance instead of automatically.',
    },
    'Ambidexterity': {
        "page": 'CT/DD02655.htm',
        "description": 'Ambidextrous characters are able to use either hand with equal coordination and skill. They are neither right-handed nor left-handed. When fighting in two-weapon style, an ambidextrous character has two “primary” hands, and suffers a –2 penalty to hit with either weapon. If the ambidextrous character spends a slot to specialize in two-weapon fighting style, he suffers no penalty to attacks with either weapon.',
    },
    'Ambush': {
        "page": 'CT/DD02656.htm',
        "description": 'A character with this proficiency is skilled at laying ambushes and setting up surprise attacks. Most characters can set up an adequate ambush when the terrain favors it and they know the enemy is coming, but a character who spends a slot on this skill is able to create ambushes where ambushes wouldn’t normally be possible. Ambushes are impossible if the attackers have already been spotted by the victims; there’s no point in hiding then. If the ambushing party knows their quarry is coming to them, they can lay an ambush. If the attack is going to take place in difficult or unusual circumstances, a proficiency check may be called for; failure indicates that the victims have spotted the ambush before they walk into it. Otherwise, the ambush is guaranteed to achieve surprise.',
    },
    'Artillerist': {
        "page": 'CT/DD02824.htm',
        "description": 'A character with this proficiency can direct the siting and operation of a bombardment engine. The maximum number of engines the character can control is equal to 1/3 of the character’s Charisma/Leadership score, provided that the engines are no farther apart than the character can sprint in a single round.',
    },
    'Backward Kick': {
        "page": 'CT/DD02705.htm',
        "description": 'The character can attack an opponent standing in one of her rear squares either by lashing backward or kicking over her own head. This maneuver does not provoke attacks of opportunity (but deliberately turning one’s back on an opponent does). This maneuver works best for characters proficient in style B, similar to the flying kick described above.',
    },
    'Camouflage': {
        "page": 'CT/DD02657.htm',
        "description": 'Characters skilled in camouflage understand how to stay out of sight in natural surroundings. Unlike hiding in shadows, camouflage requires one of two things: good cover nearby or a lot of preparation. It’s possible for a character to hide himself on a flat, rocky desert, but he’d need to have special clothes and time to ready a hiding spot. On the other hand, almost anyone can duck behind a tree on short notice. If the character passes his camouflage check, he is considered to be effectively invisible as long as he doesn’t move. He can avoid encounters if he chooses, or gain a –1 bonus on his chance to surprise someone who doesn’t spot him. The character’s check is modified as noted below: · Ground Cover: –4 penalty if no vegetation is nearby; · Terrain: +1 bonus if terrain is rocky, hilly, or broken, +2 if very rocky; · Preparation Time: –2 if character has only one round of warning, –4 if character has no warning. Rangers and thieves gain a +40% to their chance to hide in shadows if they pass a camouflage check in conjunction with their attempt to hide in shadows.',
    },
    'Crushing Blow': {
        "page": 'CT/DD02705.htm',
        "description": 'The character can break hard objects with her hands (or feet if she uses style B). Under ideal conditions, the character can break a wooden board 1/2” thick per level or 1/4” slab of stone or brick per level. Objects that are exceptionally strong, reinforced, supported by other objects (such as bricks in a wall), or not shaped like boards receive a saving throw roll vs. crushing blow to avoid breakage. When used against a creature, the crushing blow does normal damage plus 1 point per level. A crushing blow requires intense concentration. It is a no-move action, and the character can take no other actions during the round when she uses the crushing blow.',
    },
    'Dirty Fighting': {
        "page": 'CT/DD02658.htm',
        "description": 'Veteran brawlers and soldiers acquire a repertoire of feints, ruses, and various unsportsmanlike tactics that can come in handy in a fight. A character with this “skill” can attempt to use a dirty trick once per fight; if he succeeds, he gains a +1 bonus to his next attack roll. If there’s some reason the enemy believes the character will fight honorably (hardly a wise assumption!) the bonus is +2. Once a particular enemy has fallen prey to the character’s dirty trick, he can never be caught off-guard again. In addition, if the character’s opponent is skilled in dirty fighting himself, the attempt automatically fails.',
    },
    'Endurance': {
        "page": 'CT/DD02659.htm',
        "description": 'This proficiency allows a character to perform strenuous physical activity twice as long as a normal character before fatigue and exhaustion set in. If the fatigue rules from Chapter One are in play, a character with this proficiency increases his fatigue points by 50%.',
    },
    'Fine Balance': {
        "page": 'CT/DD02660.htm',
        "description": 'Characters with this talent are blessed with an innate sense of balance and have an uncanny knack for keeping their feet under them. With a successful proficiency check, the character gains a +2 bonus on any climbing checks, saving throws, or ability checks to avoid slipping or falling. In addition, the character reduces any penalties for fighting in off-balance or awkward situations by 2 points. The fine balance talent is also very useful for tightrope walking, tumbling, and climbing walls. If the DM determines that a particular feat would be influenced by the character’s exceptional balance, the character gains a +2 (on d20 rolls) or +10% (on d100 rolls) bonus to his rolls to resolve the action.',
    },
    'Flying Kick': {
        "page": 'CT/DD02705.htm',
        "description": 'The character can leap high into the air, leading with a powerful kick that can strike opponents up to three squares away. The character can land in any square adjacent to the target, as long as it is within two squares of the attacker’s starting position. If the character is not proficient in style B, this maneuver is the only attack she can make in the round, and the kick inflicts 2d4 points of damage. Strength bonuses to the attack and damage rolls apply, but specialization and mastery bonuses from another marital arts style do not. If the character is proficient in style B, this maneuver can replace one kick attack each round, and the kick inflicts 2d6 points of damage. Strength bonuses apply to the attack and damage rolls. If the character is a style B specialist or master, the appropriate bonuses also apply. If the character has at least one square of running room and declares a half move action, no ability check is required. If the character has no running room or declares a no move action, a Strength/Muscle check is required. If the ability check fails, the attack automatically misses as the character falls down in her landing square.',
    },
    'Instant Stand': {
        "page": 'CT/DD02705.htm',
        "description": 'The character can instantly regain his feet after falling down. If the ability check succeeds, the character can ignore the effects of knockdowns or failed spring attempts. If the ability check fails, the character can get up during his next action phase, but cannot take any further actions until the next round. Characters cannot use this skill while pinned, locked, held, or grappled.',
    },
    'Iron Will': {
        "page": 'CT/DD02661.htm',
        "description": 'Some people are possessed of an amazing ability to drive themselves on despite injuries or exhaustion that would stop another person in his tracks. A character with the iron will talent gains a +1 bonus to saving throws vs. mind-affecting spells or effects, including charms, holds, hypnotism, fascination, suggestion, and other such spells. In addition, characters with iron will have the unqiue ability to keep fighting even after being reduced to negative hit points. Each round that the character wishes to remain conscious, he must roll a successful saving throw vs. death with his negative hit point total as a modifier to the roll. For example, a character reduced to –5 hit points can try to stay on his feet and keep moving and fighting by succeeding on a saving throw roll with a –5 penalty. As long as the character remains conscious, his condition does not worsen—in other words, he doesn’t begin to lose 1 additional hit point per round until he actually passes out.',
    },
    'Leadership': {
        "page": 'CT/DD02662.htm',
        "description": 'Characters with the leadership talent understand how to motivate troops and get the most out of their men. In battlefield situations, a military unit led by the hero gains a +2 bonus to any morale checks they have to make. If you are playing with the mass combat rules in Chapter Eight , the character is treated as if he were three levels higher than he really is, so a 4th-level fighter can command troops as a 7th-level fighter if he possesses this talent.',
    },
    'Martial Arts: Style A': {
        "page": 'CT/DD02701.htm',
        "description": 'The style emphasizes striking with the hands or fists. The character’s bare or gloved hands are treated as small, hard objects (1d3 points of damage), and the character can strike and damage creatures of any size. If the character is unarmed and unarmored, he can make an extra attack each round with his other hand (provided that it is free) without the usual penalties for attacking with two weapons. ·',
    },
    'Martial Arts: Style B': {
        "page": 'CT/DD02701.htm',
        "description": 'The style emphasizes striking with the feet. The character’s bare or shod feet are treated as large, hard objects (1d6 points of damage), and the character can kick opponents even when they are not prone, sitting, or kneeling. If unarmed and unarmored, the character can make an extra attack each round with one of his free hands. Note that the ability to pummel creatures of any size is not part of this style. ·',
    },
    'Martial Arts: Style C': {
        "page": 'CT/DD02701.htm',
        "description": 'The style emphasizes throws and escapes. The character can choose the pull/trip combat option when making pummeling attacks. If the attack hits, the martial artist can use either his Strength or Dexterity score for the opposed roll. The martial artist also can make an opposed attack roll to escape any hold, grapple, lock, or pin. The escape roll counts as an attack, but if it succeeds the martial artist is considered clear and can finish the round normally. ·',
    },
    'Martial Arts: Style D': {
        "page": 'CT/DD02701.htm',
        "description": 'The style emphasizes dodges and blocks. The character can make one free block each round in addition to any attacks he makes. If unarmed and unarmored, the character receives a –2 Armor Class bonus.',
    },
    'Missile Deflection': {
        "page": 'CT/DD02705.htm',
        "description": 'The character can perform block maneuvers (see Chapter Two ) against normal missiles fired at her from the front. The character can use her free change of facing (see Chapter One ) to turn toward an attacker firing missiles from her flank or rear, but this counts as her change of facing for the round. Normal missiles include mundane and enchanted arrows, axes, bolts, javelins, small stones, and spears. Large or magical missiles, such as ballista bolts, hurled boulders, and magic missile spells, cannot be deflected.',
    },
    'Missile or Thrown Weapon': {
        "page": 'CT/DD02650.htm',
        "description": 'Some heroes specialize in fighting with ranged weapons; Robin Hood and William Tell spring to mind as good examples. Characters who choose to specialize in missile or thrown weapon style gain two benefits. First, they can move up to half their normal movement rate and still attack with their full rate of fire, or make a full move and attack at half their rate of fire. Second, they gain a bonus of –1 to their AC against enemy missile fire while attacking with a ranged weapon.',
    },
    'One-Handed Weapon': {
        "page": 'CT/DD02647.htm',
        "description": 'The character is always free to treat his empty hand as a “secondary weapon” and punch, grab, or otherwise annoy anyone he is fighting. The normal penalties for using two weapons apply. If the character is also familiar with the two-handed weapon style and his weapon can be used either one- or two-handed, he can switch back and forth between the two styles at the beginning of every round of combat. Characters who specialize in this style gain a special AC bonus of +1 while fighting with a one-handed weapon and no shield or off-hand weapon. By spending an additional proficiency slot, the character can increase his AC bonus to +2, but that’s the maximum benefit for style specialization.',
    },
    'Overbearing': {
        "page": 'CT/DD02689.htm',
        "description": 'This version of overbearing is an expanded version of the one appearing in Chapter Two , but it also assumes that no combatants involved are fighting with weapons. Overbearing includes most attacks aimed at simply overpowering the target. If the attackers are seeking to overwhelm the defender through brute strength or sheer weight of numbers, it’s an overbearing attack. Overbearing is a tactic available to any creature and can be used against almost any other creature. Creatures with multiple legs are difficult to overbear. Creatures with no legs at all are nearly impossible to overbear (because they can’t be knocked down) but attackers with sufficient strength sometimes can pin them in place. Creatures with no solid form (immaterial, gaseous, or liquid) cannot be overborne. Characters need not have their hands free to make overbearing attacks, but they might not be able to take full advantage of pins if they do not ( see below ).',
    },
    'Pummeling': {
        "page": 'CT/DD02672.htm',
        "description": 'Pummeling includes most attacks made with hands, fists, elbows, and the like. Humanoid and partially humanoid creatures with racial intelligence of at least low can make pummeling attacks. Nonhumanoid creatures with racial intelligence of at least average and with manipulative appendages at least as large and strong as human hands and arms also can pummel. Humans, demihumans, orcs, ogres, giants, centaurs, and similar creatures can make pummeling attacks. Great cats, octopi, oozes, horses, and other creatures who lack intelligence or prehensile appendages cannot. Common sense must apply. For example, the DM might allow androsphinxes to make pummeling attacks if they retract their claws. Generally, however, creatures with natural attacks use them in preference to pummeling attacks. Pummeling requires at least one free hand, although the attacker may wear a metal gauntlet or similar item. A character may also use a weapon pommel or an improvised weapon, such as a mug or bottle, in a pummeling attack. Attacks with improvised weapons provoke attacks of opportunity just as other brawling attacks do. The target of a pummeling attack must be alive, non-vegetable, organic, and non-fluid. Undead, shambling mounds, golems, and jellies are among the many creatures that cannot be pummeled. Pummeling is ineffective against creatures who can be harmed only by special or magical weapons unless the attacker functions as a magical weapon powerful enough to hurt the creature (see DMG , Table 46; note that character levels never apply to the table). Elementals, fiends, and most extraplanar creatures are immune to pummeling unless attacked by similar creatures or by characters using magical weapons. Creatures immune to blunt (type B) weapons are immune to pummeling attacks. No creature can pummel an opponent more than one size larger than itself unless the target is not standing up (prone, kneeling, or sitting) or the attacker has a height advantage or can fly. For example, a halfling usually cannot pummel a hill giant.',
    },
    'Quickness': {
        "page": 'CT/DD02663.htm',
        "description": 'A character with this talent is unusually fast. Her hand-eye coordination is excellent, and she can often get past her opponent’s defenses before they realize how quick she really is. In combat, she gains a special –2 bonus to her initiative roll if she makes a proficiency check. She can use this bonus if she moves or makes an attack with a weapon of average speed or quicker, but her special bonus does not apply to attacks with slow weapons or stationary actions such as guarding or parrying.',
    },
    'Spring': {
        "page": 'CT/DD02705.htm',
        "description": 'The character can make astonishing jumps and leaps with blinding speed. At the cost of a half move or an attack, the character can spring into the air, attaining a height of five feet and landing up to two squares away in any direction. The character can flip and twist while airborne to achieve any facing when he lands. If the character has a 2-square running start, he can double his springing distance, landing up to four squares away and leaping 10 feet in the air, but the running start is a half-move action. For every additional slot spent on this skill, the character can add five feet and one square to the distance achieved. For example, a character who as spent two slots on this skill could leap 10 feet into the air and land up to three squares away from a standing start. If the character’s Dexterity/Balance roll fails, the character falls down in his landing square; he can get up during his next action phase, but can take no other actions until the following round. If the ability check succeeds, the character can finish the round normally after landing.',
    },
    'Steady Hand': {
        "page": 'CT/DD02664.htm',
        "description": 'Characters with this talent are excellent shots with bows or crossbows. They have an unusually good eye for distance, a knack for judging a tricky shot, and a smooth and easy aim and release. If the character takes a full round to aim his shot (i.e., voluntarily holds his action until last in the round) he suffers no penalty for a medium-range shot and only a –2 penalty for a long-range shot. If the character would normally receive multiple attacks with his weapon, he has to forfeit them in order to use this talent—he can make only one shot per round.',
    },
    'Trouble Sense': {
        "page": 'CT/DD02665.htm',
        "description": 'Sometimes known as a danger sense, this talent gives the character a chance to detect otherwise undetectable threats by instinct. The character’s trouble sense comes into play when the character is threatened by a danger he hasn’t noticed yet. The DM should make trouble sense checks in secret. If the character succeeds, he is only surprised on a roll of 1 by a sneak attack and treats any rear attacks as flank attacks instead. The DM can modify the proficiency check if the character is taking extra precautions or if the attacker would be particularly hard to notice before striking.',
    },
    'Two-Handed Weapon': {
        "page": 'CT/DD02648.htm',
        "description": 'Many weapons are so large that a character is required to use both hands to wield them. The rule of thumb is simple: a character can use a weapon with a size equal to or less than her own in one hand and can use a weapon one size larger than herself if she wields it two-handed. If a character specializes in two-handed weapon style, she increases the speed of her weapon by one category (slow to average, average to fast) when she fights using a two-handed weapon. If you’re not using the new initiative rules presented in Chapter One , the weapon’s speed factor drops by 3. There are a few weapons that can normally be employed one-handed or two-handed; these are noted in the weapons list of Chapter Seven . There are also a variety of weapons that are normally used one-handed but that can be used two-handed. This would allow a specialist in this style to gain the speed benefit mentioned above. In addition, the two-handed style specialist gains a +1 to damage rolls when using a one-handed weapon in two hands.',
    },
    'Two-Weapon': {
        "page": 'CT/DD02649.htm',
        "description": 'This is a difficult style to master, since it requires exceptional coordination and skill. Normally, characters who fight with a weapon in each hand suffer a –2 penalty to attacks with their primary hand and a –4 penalty to attacks with the off-hand weapon. This can be partially or completely negated by the character’s reaction adjustment for Dexterity (or Dex/Aim if you’re also using Skills & Powers ). Characters who specialize in this style reduce their penalty to 0 and –2, respectively. Ambidextrous characters who specialize in this style suffer no penalty with either attack. The character’s secondary weapon must be one size smaller than his primary weapon—but knives and daggers can always be used as secondary weapons, regardless of the size of the primary weapon. Note that this means that for Man-sized characters, the secondary weapon has to be size S. However, if a character spends a second proficiency slot on two-weapon style specialization, he gains the ability to use two weapons of equal size, as long as he can use each one as a one-handed weapon. Rangers are considered to have the first slot of this style specialization for free as a character ability.',
    },
    'Vehicle Handling': {
        "page": 'CT/DD02824.htm',
        "description": 'This proficiency allows the character to control a wagon or chariot under difficult circumstances. The character can roll against this proficiency when a driving check is normally required.',
    },
    'Weapon and Shield': {
        "page": 'CT/DD02646.htm',
        "description": 'Normally, a character employing a shield in his off hand can shield-rush, shield-punch, block, or trap as if it were a secondary weapon, with the normal penalties for attacking with two weapons. The disadvantage is that the shield’s AC bonus is forfeited for any round in which it is used this way. However, characters who specialize in weapon and shield style can choose to make one of these secondary attacks every round without losing the AC benefit for carrying a shield. If the heroic fray rules from Chapter Two are in use, the character only gets one secondary attack, not two, but his primary weapon attacks are still doubled, of course.',
    },
    'Wrestling': {
        "page": 'CT/DD02679.htm',
        "description": 'Wrestling includes all attacks aimed at grasping and holding an opponent. Any creature with racial intelligence of at least semi- can make wrestling attacks if it also has grasping appendages that it could use to restrain an opponent. Incorporeal and amorphous creatures cannot make wrestling attacks and cannot be wrestled. Limbless creatures, such as worms, snakes, and the like, generally cannot wrestle, though constrictor snakes can be assumed to be using a form of wrestling. Wormlike and snakelike creatures are resistant to wrestling damage, but can be held or locked so they cannot attack until they win free of the hold. Creatures immune to normal weapons have a natural resistance to wrestling attacks, so they can be grappled or pinned but take no damage from a hold unless the attacker functions as a magical weapon. Immunity to normal weapons, however, does not protect a creature from the effects of a lock, including damage. Wrestling requires both hands free. Shields, which are normally worn strapped to the forearm, interfere with the character’s grip and prevent wrestling. Wrestling combat always takes place between two opponents; multiple attackers cannot make a wrestling attack as a group. Damage from wrestling holds and locks is mostly temporary, just like other types of brawling damage.',
    },
}
