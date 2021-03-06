"""
Tests for the turn order functions.
"""
import pytest

import dice.exc
import dice.turn
from dice.turn import TurnUser, TurnOrder, TurnEffect


def test_break_init_tie_modifier_differ():
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 27

    assert dice.turn.break_init_tie(user, user2) == (user, user2)
    assert dice.turn.break_init_tie(user2, user) == (user, user2)


def test_break_init_tie_modifier_same():
    user = TurnUser('Chris', 2)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 27

    winner, loser = dice.turn.break_init_tie(user, user2)
    assert winner.modifier == loser.modifier
    assert winner.init > loser.init


def test_find_user_by_name():
    users = [TurnUser("Chris", 7), TurnUser("Chris' Pet", 2),
             TurnUser("Orc", 7), TurnUser("Orc2", 2)]
    dice.turn.find_user_by_name(users, "Orc2")


def test_find_user_by_name_raises():
    users = [TurnUser("Chris", 7), TurnUser("Chris' Pet", 2),
             TurnUser("Orc", 7), TurnUser("Orc2", 2)]

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.turn.find_user_by_name(users, "Chris")

    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.turn.find_user_by_name(users, "Dwarf")


def test_users_same_init():
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 10
    users = [user, user2]

    assert not dice.turn.users_same_init(users)
    user2.init = 27
    assert dice.turn.users_same_init(users)


def test_parse_turn_users():
    tokens = ['Chris/7', 'Noggles/3/20']
    users = dice.turn.parse_turn_users(tokens)

    assert users[0].name == 'Chris'
    assert users[0].modifier == 7
    assert dice.turn.TurnUser('Noggles', 3, 20) == users[1]


def test_parse_turn_users_errors():
    tokens = ['Chris/notNumber']
    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.turn.parse_turn_users(tokens)

    tokens = ['Chris']
    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.turn.parse_turn_users(tokens)


def test_turn_effect__repr__():  # covers __init__ too, quite simple
    effect = dice.turn.TurnEffect('poison', 3)

    assert repr(effect) == "TurnEffect(text='poison', turns=3)"


def test_turn_effect__str__():
    effect = dice.turn.TurnEffect('poison', 3)

    assert str(effect) == 'poison: 3'


def test_turn_effect__eq__():
    effect = dice.turn.TurnEffect('poison', 3)
    effect2 = dice.turn.TurnEffect('poison', 1)

    assert effect == effect2


def test_turn_effect__lt__():
    effect = dice.turn.TurnEffect('poison', 3)
    effect2 = dice.turn.TurnEffect('on fire', 1)

    assert effect > effect2


def test_turn_effect__hash__():
    effect = dice.turn.TurnEffect('poison', 3)

    assert hash(effect) == hash(effect.text)


def test_turn_effect__add__():
    effect = dice.turn.TurnEffect('poison', 3)
    n_effect = effect + 1

    assert effect.turns == n_effect.turns - 1
    assert n_effect.turns == 4


def test_turn_effect__sub__():
    effect = dice.turn.TurnEffect('poison', 3)
    n_effect = effect - 1

    assert effect.turns == n_effect.turns + 1
    assert n_effect.turns == 2


def test_turn_effect__radd__():
    effect = dice.turn.TurnEffect('poison', 3)
    n_effect = 1 + effect

    assert effect.turns == n_effect.turns - 1
    assert n_effect.turns == 4


def test_turn_effect__iadd__():
    effect = dice.turn.TurnEffect('poison', 3)
    effect += 1

    assert effect.turns == 4


def test_turn_effect__isub__():
    effect = dice.turn.TurnEffect('poison', 3)
    effect -= 1

    assert effect.turns == 2


def test_turn_effect_is_expired():
    effect = dice.turn.TurnEffect('poison', 1)
    assert not effect.is_expired()

    effect -= 1
    assert effect.is_expired()


def test_tuser__init__():
    user = TurnUser('Chris', 7)
    assert user.init in list(range(7, 28))
    user = TurnUser('Chris', 7, 22)
    assert user.init == 22
    user = TurnUser('Chris', 7, 22, ['poison'])
    assert user.effects == ['poison']


def test_tuser__repr__():
    user = TurnUser('Chris', 7)
    user.init = 27
    assert repr(user) == "TurnUser(name='Chris', modifier=7, init=27, effects=[])"

    user.add_effect('Poison', 3)
    assert repr(user) == "TurnUser(name='Chris', modifier=7, init=27, effects=[TurnEffect(text='Poison', turns=3)])"


def test_tuser__str__():
    user = TurnUser('Chris', 7)
    user.init = 27
    assert str(user) == 'Chris (7): 27.00'

    user.add_effect('Poison', 3)
    assert str(user) == 'Chris (7): 27.00\n        Poison: 3'


def test_tuser__eq__():
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 27
    user3 = TurnUser('Chris', 7)
    user3.init = 27

    assert user != user2
    assert user == user3


def test_tuser__ne__():
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 10

    assert user2 != user


def test_tuser__lt__():
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 10

    assert user2 < user


def test_tuser_roll_init():
    user = TurnUser('Chris', 7)
    old = user.init
    while user.init == old:
        user.roll_init()

    assert user.init != old


def test_tuser_add_effect():
    user = TurnUser('Chris', 7, 27)
    user.add_effect('Poison', 4)

    assert str(user.effects) == "[TurnEffect(text='Poison', turns=4)]"

    with pytest.raises(dice.exc.InvalidCommandArgs):
        user.add_effect('Stun', 0)
    with pytest.raises(dice.exc.InvalidCommandArgs):
        user.add_effect('Stun', -4)
    with pytest.raises(dice.exc.InvalidCommandArgs):
        user.add_effect('Poison', 3)


def test_tuser_update_effect():
    user = TurnUser('Chris', 7, 27)
    user.add_effect('Poison', 4)

    assert str(user.effects) == "[TurnEffect(text='Poison', turns=4)]"

    user.update_effect('Poison', 1)
    assert str(user.effects) == "[TurnEffect(text='Poison', turns=1)]"


def test_tuser_remove_effect():
    user = TurnUser('Chris', 7, 27)
    user.add_effect('Poison', 4)

    assert str(user.effects) == "[TurnEffect(text='Poison', turns=4)]"

    user.remove_effect('Poison')
    assert str(user.effects) == "[]"


def test_tuser_decrement_effects():
    user = TurnUser('Chris', 7, 27)
    user.add_effect('Poison', 1)
    user.add_effect('Rufus', 2)

    expect = [TurnEffect(text='Poison', turns=1), TurnEffect(text='Rufus', turns=2)]
    assert user.effects == expect

    assert user.decrement_effects() == expect[:1]
    assert user.effects == [TurnEffect(text='Rufus', turns=1)]


def test_torder__init__():
    order = TurnOrder()
    assert order.users == []
    assert order.cur_user is None


def test_torder__str__():
    order = TurnOrder()
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 10
    order.users = list(reversed(sorted([user, user2])))

    expect = """__**Turn Order**__

```  name    | mod. | init
--------- | ---- | -----
> Chris < | +7   | 27.00
Orc       | +2   | 10.00```"""
    assert str(order) == expect


def test_torder__repr__():
    order = TurnOrder()
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 10
    order.users = list(reversed(sorted([user, user2])))

    expect = "TurnOrder(users=[TurnUser(name='Chris', modifier=7, init=27, effects=[]), "\
             "TurnUser(name='Orc', modifier=2, init=10, effects=[])], "\
             "user_index=0)"
    assert repr(order) == expect


def test_torder_does_name_exist():
    order = TurnOrder()
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Chris', 2)
    user2.init = 10

    order.add(user)
    with pytest.raises(dice.exc.InvalidCommandArgs):
        order.add(user2)


def test_torder_add_empty():
    order = TurnOrder()
    user = TurnUser('Chris', 7)
    user.init = 27
    order.add(user)

    assert user in order.users


def test_torder_add_second():
    order = TurnOrder()
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 10
    order.add(user)
    order.add(user2)

    assert user in order.users
    assert user2 in order.users


def test_torder_add_all_diff_modifiers():
    order = TurnOrder()
    user = TurnUser('Chris', 7, 10)
    user2 = TurnUser('Orc', 2, 10)
    user3 = TurnUser('Dwarf', 3, 10)
    order.add_all([user, user2, user3])

    assert 'Chris' in str(order)
    assert 'Orc' in str(order)
    assert 'Dwarf' in str(order)


def test_torder_add_all_same():
    order = TurnOrder()
    user = TurnUser('Chris', 4, 10)
    user2 = TurnUser('Orc', 4, 10)
    user3 = TurnUser('Dwarf', 4, 10)
    order.add_all([user, user2, user3])

    assert user.init != user2.init
    assert user2.init != user3.init
    assert user.init != user3.init


def test_turn_add_collide_on_addition():
    order = TurnOrder()
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 27
    user3 = TurnUser('Orc2', 2)
    user3.init = 27
    user4 = TurnUser('Orc3', 2)
    user4.init = 27
    order.add(user)
    order.add(user2)
    order.add(user3)
    order.add(user4)

    assert order.users[0] == user
    for a_user in [user, user2, user3, user4]:
        assert a_user in order.users


def test_torder_next():
    order = TurnOrder()
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 10
    order.add(user)
    order.add(user2)

    assert order.cur_user == user
    assert order.next() == user2
    assert order.cur_user == user2
    assert order.next() == user
    assert order.cur_user == user


def test_torder_next_empty_users():
    order = TurnOrder()

    with pytest.raises(dice.exc.InvalidCommandArgs):
        order.next()


def test_torder_remove_current():
    order = TurnOrder()
    user = TurnUser('Chris', 7, 27)
    user2 = TurnUser('Dwarf', 3, 12)
    user3 = TurnUser('Orc', 2, 10)
    order.add_all([user, user2, user3])
    order.next()
    assert order.user_index == 1
    assert order.cur_user == user2

    order.remove(user2.name)

    assert order.user_index == 1
    assert user in order.users
    assert user2 not in order.users
    assert user3 in order.users
    assert order.cur_user == user3


def test_torder_remove_prev():
    order = TurnOrder()
    user = TurnUser('Chris', 7, 27)
    user2 = TurnUser('Dwarf', 3, 12)
    user3 = TurnUser('Orc', 2, 10)
    order.add_all([user, user2, user3])
    order.next()
    assert order.user_index == 1
    assert order.cur_user == user2

    order.remove(user.name)

    assert order.user_index == 0
    assert user not in order.users
    assert user2 in order.users
    assert user3 in order.users
    assert order.cur_user == user2


def test_torder_remove_last():
    order = TurnOrder()
    user = TurnUser('Chris', 7, 27)
    user2 = TurnUser('Dwarf', 3, 12)
    user3 = TurnUser('Orc', 2, 10)
    order.add_all([user, user2, user3])
    order.next()
    order.next()
    assert order.user_index == 2
    assert order.cur_user == user3

    order.remove(user3.name)

    assert order.user_index == 0
    assert user in order.users
    assert user2 in order.users
    assert user3 not in order.users
    assert order.cur_user == user


def test_torder_update_user():
    order = TurnOrder()
    user = TurnUser('Chris', 7, 27)
    user2 = TurnUser('Orc', 2, 10)
    user3 = TurnUser('Dwarf', 3, 12)
    order.add_all([user, user2, user3])
    order.update_user('ris', 1)

    assert user.init == 1
    assert order.users[-1] == user


def test_torder_update_user_raises():
    order = TurnOrder()
    user = TurnUser('Chris', 7, 27)
    user2 = TurnUser('Orc', 2, 10)
    user3 = TurnUser('Dwarf', 3, 12)
    order.add_all([user, user2, user3])

    with pytest.raises(dice.exc.InvalidCommandArgs):
        order.update_user('r', 1)

    with pytest.raises(dice.exc.InvalidCommandArgs):
        order.update_user('Chris', 'a')
