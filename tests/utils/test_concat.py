from auryn.utils import and_, or_


def test_and_none() -> None:
    for empty in ([], set(), (i for i in range(1, 1))):
        assert and_(empty) == "<none>"


def test_and_one() -> None:
    for one in ([1], {1}, (i for i in range(1, 2))):
        assert and_(one) == "1"


def test_and_two() -> None:
    for two in ([1, 2], {1, 2}, (i for i in range(1, 3))):
        assert and_(two) == "1 and 2"


def test_and_many() -> None:
    for many in ([1, 2, 3], {1, 2, 3}, (i for i in range(1, 4))):
        assert and_(many) == "1, 2 and 3"


def test_and_quote() -> None:
    items = ["a", "b", "c"]
    assert and_(items) == "a, b and c"
    assert and_(items, quote=True) == "'a', 'b' and 'c'"


def test_or_none() -> None:
    for empty in ([], set(), (i for i in range(1, 1))):
        assert or_(empty) == "<none>"


def test_or_one() -> None:
    for one in ([1], {1}, (i for i in range(1, 2))):
        assert or_(one) == "1"


def test_or_two() -> None:
    for two in ([1, 2], {1, 2}, (i for i in range(1, 3))):
        assert or_(two) == "1 or 2"


def test_or_many() -> None:
    for many in ([1, 2, 3], {1, 2, 3}, (i for i in range(1, 4))):
        assert or_(many) == "1, 2 or 3"


def test_or_quote() -> None:
    items = ["a", "b", "c"]
    assert or_(items) == "a, b or c"
    assert or_(items, quote=True) == "'a', 'b' or 'c'"
