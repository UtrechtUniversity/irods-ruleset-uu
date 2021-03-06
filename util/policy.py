# -*- coding: utf-8 -*-
"""Utilities for creating PEP rules."""

__copyright__ = 'Copyright (c) 2019, Utrecht University'
__license__   = 'GPLv3, see LICENSE'

import api
import log
import rule


class Succeed(object):
    """Policy function result, indicates success.

    Evaluates to True in boolean context.
    """

    def __str__(self):
        return 'Action permitted'

    def __bool__(self):
        return True
    __nonzero__ = __bool__


class Fail(object):
    """Policy function result, indicates failure.

    As a result, the PEP-instrumented operation will be aborted, and
    pep_x_except will fire.

    Evaluates to False in boolean context.
    """

    def __init__(self, reason):
        self.reason = reason

    def __str__(self):
        return 'Action not permitted: ' + self.reason

    def __bool__(self):
        return False
    __nonzero__ = __bool__


# Functions to be used to instantiate the above result types.
fail    = Fail
succeed = Succeed


def all(*x):
    for i in x:
        if not i:
            return i
    return succeed()


def require():
    """Turn a function into a PEP rule that fails unless policy.succeed() is returned.

    The function must explicitly return policy.succeed() or .fail('reason') as a result.
    Any other return type will result in the PEP failing (blocks associated action).

    :returns: Decorator to turn a function into a PEP rule that fails unless policy.succeed() is returned
    """
    def deco(f):
        @rule.make(outputs=[])
        def r(ctx, *args):
            """Execute a function as a PEP rule.

            :param ctx:  Combined type of a callback and rei struct
            :param args: Arguments of function

            :raises api.Error:      Unhandled API error
            :raises AssertionError: Policy did not succeed

            :returns: Result of function as PEP rule
            """
            try:
                result = f(ctx, *args)
            except api.Error as e:
                log._write(ctx, '{} failed due to unhandled API error: {}'.format(f.__name__, str(e)))
                raise
            except Exception as e:
                log._write(ctx, '{} failed due to unhandled internal error: {}'.format(f.__name__, str(e)))
                raise

            if isinstance(result, Succeed):
                return  # succeed the rule (msi "succeed" has no effect here)
            elif isinstance(result, Fail):
                log._write(ctx, '{} denied: {}'.format(f.__name__, str(result)))
                ctx.msiOprDisallowed()
                raise AssertionError()  # Just in case.

            # Require an unambiguous YES from the policy function.
            # Default to fail.
            log._write(ctx, '{} denied: ambiguous policy result (internal error): {}'
                            .format(f.__name__, str(result)))
            ctx.msiOprDisallowed()
            raise AssertionError()
        return r
    return deco
