import check_deps


def test_no_missing_in_dev_env():
    assert check_deps.missing() == []
