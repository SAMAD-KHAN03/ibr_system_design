import os
from functools import wraps
from pathlib import Path

from os.path import dirname, realpath, exists
from os import mkdir, environ
from typing import Callable, Any

import pandas as pd

from inspect import isgeneratorfunction, getfile


WRITE_DATA = bool(environ.get('STABILITY_WRITE_DATA'))


def stability_test(
    func=None,
    write: bool = False,
    test_case: str = None,
    **kwargs,
):
    if isinstance(func, Callable):
        # Has been called "directly":
        #   @stability_test
        #   def test_...():
        return get_wrapped_func(func, write, test_case, **kwargs)
    else:
        # Has been called with arguments:
        #   @stability_test(test_case=...)
        #   def test_...():
        def dec(f):
            return get_wrapped_func(f, write, test_case, **kwargs)
        return dec


def get_wrapped_func(
    func: Callable,
    write: bool = False,
    test_case=None,
    **dec_kwargs,
):
    @wraps(func)
    def wrapped(*func_args, **func_kwargs):
        out = func(*func_args, **func_kwargs)

        if isgeneratorfunction(func):
            for i, yielded in enumerate(out):
                assert_output_equals_expected(
                    yielded,
                    func,
                    write,
                    test_case=i,
                    **dec_kwargs,
                )
        else:
            assert_output_equals_expected(
                out,
                func,
                write,
                test_case=test_case,
                **dec_kwargs,
            )

    return wrapped


def assert_output_equals_expected(
    out: pd.DataFrame,
    func: Callable,
    write: bool,
    test_case: int | str,
    **dec_kwargs,
):
    run_output_checks(out)
    out = convert_dtypes(out)

    filepath = get_expected_csv_filepath(func, test_case)

    if WRITE_DATA or write:
        out.to_csv(filepath, index=False)

    expec = pd.read_csv(filepath)
    pd.testing.assert_frame_equal(out, expec, **dec_kwargs)


def run_output_checks(out):
    error = (
        "Only dataframes can be used with the `stability_test` decorator, "
        f"found output of type {type(out)}."
    )
    assert isinstance(out, pd.DataFrame), error

    error = (
        "Dataframes for use with the `stability_test` decorator should "
        f"always have a 0...n-1 range index, found {out.index}."
    )
    valid_index = pd.RangeIndex(len(out))
    assert out.index.equals(valid_index), error


def convert_dtypes(df):
    """
    Because we will compare to the output of a CSV file,
    we convert timestamps to strings. This means that the
    decorator cannot pick up on cases where the dtype of
    one of the columns being checked has changed from
    datetime64 to str, but the user has been warned
    about this in the README.
    """
    df = df.copy()

    dtypes = ["datetime64", "datetimetz"]
    datetime_df = df.select_dtypes(dtypes)
    date_columns = datetime_df.columns

    df[date_columns] = datetime_df.astype(str)

    return df


def get_expected_csv_filepath(func, test_case=None):
    test_filepath = getfile(func)
    test_filename = test_filepath.split(os.sep)[-1].split('.')[0]

    folder = full_path(test_filepath) / 'resources'
    if not exists(folder):
        mkdir(folder)

    test_name = func.__name__

    suffix = "" if test_case is None else f"_{test_case}"
    csv_filename = f"{test_filename}_{test_name}{suffix}.csv"

    csv_filepath = folder / csv_filename
    return csv_filepath


def full_path(file: str) -> Path:
    return Path(dirname(realpath(file)))



