import os

import pandas as pd
from pytest import fixture, mark


from src.stability.decorators import stability_test

@fixture
def my_fixture():
    multiplier = 3
    df = pd.DataFrame({'col': [10, 20, 30]})
    out = multiplier * df
    return out


@stability_test
def test_expected_decorator_basics():
    df = pd.DataFrame({
        'str_col': ['a', 'b'],
        'int_col': [1, 2],
        'float_col': [3.14159, -1],
        'datetime_col': ['2000-01-01 00:00:00', '2001-01-01 12:34:56'],
    })
    df['datetime_col'] = pd.to_datetime(df['datetime_col'])  # [ns]

    df['datetime_col2'] = df['datetime_col'].dt.tz_localize('UTC')  # [ns, UTC]
    df['datetime_col3'] = pd.Timestamp('2000-01-01')  # [s]
    return df


@stability_test
def test_expected_decorator_with_fixture(my_fixture):
    out = 2 * my_fixture
    return out


@stability_test
def test_expected_decorator_yielding():
    df = pd.DataFrame({
        'str_col': ['a', 'b'],
        'int_col': [1, 2],
    })
    yield df

    df = pd.DataFrame({
        'float_col': [3.14159, -1],
    })
    yield df


@mark.parametrize(
    ['test_case', 'df'],
    [
        (
            0,
            pd.DataFrame({
                'str_col': ['a', 'b'],
                'int_col': [1, 2],
            }),
        ),
        (
            1,
            pd.DataFrame({
                'float_col': [3.14159, -1],
            }),
        ),
    ]
)
def test_expected_decorator_parametrized(test_case, df):

    @stability_test(test_case=test_case)
    def test_expected_decorator_parametrized_inner():
        return df

    test_expected_decorator_parametrized_inner()


@mark.xfail  # output is not a dataframe
@stability_test
def test_expected_decorator_output_not_a_dataframe():
    return 42


@mark.xfail  # output index is not 0...n-1
@stability_test
def test_expected_decorator_output_index_invalid():
    return pd.DataFrame({
        'float_col': [3.14159, -1],
    }, index=['a', 'b'])
