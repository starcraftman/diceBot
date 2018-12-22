"""
Tests for the turn order functions.
"""
import pytest

import dice.exc
import dice.turn
from dice.turn import TurnUser, TurnOrder


def test_break_init_tie_offset_differ():
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 27

    assert dice.turn.break_init_tie(user, user2) == (user, user2)
    assert dice.turn.break_init_tie(user2, user) == (user, user2)


def test_break_init_tie_offset_same():
    user = TurnUser('Chris', 2)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 27

    winner, loser = dice.turn.break_init_tie(user, user2)
    assert winner.offset == loser.offset
    assert winner.init > loser.init


def test_parse_turn_users():
    tokens = ['Chris/7', 'Noggles/3/20']
    users = dice.turn.parse_turn_users(tokens)

    assert users[0].name == 'Chris'
    assert users[0].offset == 7
    assert dice.turn.TurnUser('Noggles', 3, 20) == users[1]


def test_parse_turn_users_errors():
    tokens = ['Chris/notNumber']
    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.turn.parse_turn_users(tokens)

    tokens = ['Chris']
    with pytest.raises(dice.exc.InvalidCommandArgs):
        dice.turn.parse_turn_users(tokens)


def test_tuser_roll_create():
    user = TurnUser('Chris', 7)
    assert user.init in list(range(7, 28))
    user = TurnUser('Chris', 7, 22)
    assert user.init == 22


def test_tuser_last_roll():
    user = TurnUser('Chris', 7)
    assert user.last_roll in list(range(1, 21))


def test_tuser_roll_init():
    user = TurnUser('Chris', 7)
    assert user.init in list(range(7, 28))


def test_tuser__str__():
    user = TurnUser('Chris', 7)
    user.init = 27
    assert str(user) == 'Chris (7): 27.00'


def test_tuser__eq__():
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 27
    user3 = TurnUser('Chris', 7)
    user3.init = 27

    assert not user == user2
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


def test_torder_create():
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
    order.next()

    expect = """__**Turn Order**__

```  name    | mod. | init
--------- | ---- | -----
> Chris < | +7   | 27.00
Orc       | +2   | 10.00```"""
    assert str(order) == expect


def test_torder_duplicate_inits():
    order = TurnOrder()
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 10
    order.users = reversed(sorted([user, user2]))

    assert not order.duplicate_inits()
    user2.init = 27
    order.users = reversed(sorted([user, user2]))
    assert order.duplicate_inits()


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


def test_turn_add_collide():
    order = TurnOrder()
    user = TurnUser('Chris', 7)
    user.init = 27
    user2 = TurnUser('Orc', 2)
    user2.init = 27
    order.add(user)
    order.add(user2)

    assert order.users == [user, user2]


def test_turn_add_collide_on_decrement():
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

    assert order.cur_user is None
    assert order.next() == user
    assert order.cur_user == user
    assert order.next() == user2
    assert order.cur_user == user2
    assert order.next() == user
    assert order.cur_user == user


def test_torder_next_empty_users():
    order = TurnOrder()

    with pytest.raises(dice.exc.InvalidCommandArgs):
        order.next()


def test_torder_remove():
    order = TurnOrder()
    user = TurnUser('Chris', 7, 27)
    user2 = TurnUser('Orc', 2, 10)
    user3 = TurnUser('Dwarf', 3, 12)
    order.cur_user = user2
    order.add_all([user, user2, user3])
    order.remove('Orc')

    assert user in order.users
    assert user2 not in order.users
    assert order.cur_user == user
