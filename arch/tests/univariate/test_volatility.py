import warnings

import numpy as np
import pytest
from numpy.random import RandomState
from numpy.testing import assert_almost_equal, assert_equal, assert_allclose, \
    assert_array_equal
from scipy.special import gamma, gammaln

from arch.compat.python import PY3, range
try:
    from arch.univariate import _recursions as rec
except ImportError:
    from arch.univariate import recursions_python as rec
from arch.univariate.volatility import GARCH, ARCH, HARCH, ConstantVariance, \
    EWMAVariance, RiskMetrics2006, EGARCH, FixedVariance, MIDASHyperbolic
from arch.univariate.distribution import Normal, StudentsT, SkewStudent
from arch.utility.exceptions import InitialValueWarning


class TestVolatiltyProcesses(object):
    @classmethod
    def setup_class(cls):
        cls.rng = RandomState(1234)
        cls.T = 1000
        cls.resids = cls.rng.randn(cls.T)
        cls.resid_var = np.var(cls.resids)
        cls.sigma2 = np.zeros_like(cls.resids)
        cls.backcast = 1.0

    def test_garch(self):
        garch = GARCH()

        sv = garch.starting_values(self.resids)
        assert_equal(sv.shape[0], garch.num_params)

        bounds = garch.bounds(self.resids)
        assert_equal(bounds[0], (0.0, 10.0 * np.mean(self.resids ** 2.0)))
        assert_equal(bounds[1], (0.0, 1.0))
        assert_equal(bounds[2], (0.0, 1.0))
        backcast = garch.backcast(self.resids)
        w = 0.94 ** np.arange(75)
        assert_almost_equal(backcast,
                            np.sum((self.resids[:75] ** 2) * (w / w.sum())))
        var_bounds = garch.variance_bounds(self.resids)
        parameters = np.array([.1, .1, .8])
        garch.compute_variance(parameters, self.resids, self.sigma2,
                               backcast, var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        rec.garch_recursion(parameters,
                            self.resids ** 2.0,
                            np.sign(self.resids),
                            cond_var_direct,
                            1, 0, 1, self.T, backcast, var_bounds)
        assert_allclose(self.sigma2, cond_var_direct)

        a, b = garch.constraints()
        a_target = np.vstack((np.eye(3), np.array([[0, -1.0, -1.0]])))
        b_target = np.array([0.0, 0.0, 0.0, -1.0])
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)
        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = garch.simulate(parameters, self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        initial_value = 1.0
        sigma2 = np.zeros(self.T + 500)
        data = np.zeros(self.T + 500)
        for t in range(self.T + 500):
            sigma2[t] = parameters[0]
            shock = initial_value if t == 0 else data[t - 1] ** 2.0
            sigma2[t] += parameters[1] * shock
            lagged_value = initial_value if t == 0 else sigma2[t - 1]
            sigma2[t] += parameters[2] * lagged_value
            data[t] = e[t] * np.sqrt(sigma2[t])
        data = data[500:]
        sigma2 = sigma2[500:]
        assert_almost_equal(data / sim_data[0], np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

        names = garch.parameter_names()
        names_target = ['omega', 'alpha[1]', 'beta[1]']
        assert_equal(names, names_target)

        assert isinstance(garch.__str__(), str)
        txt = garch.__repr__()
        assert str(hex(id(garch))) in txt

        assert_equal(garch.name, 'GARCH')
        assert_equal(garch.num_params, 3)
        assert_equal(garch.power, 2.0)
        assert_equal(garch.p, 1)
        assert_equal(garch.o, 0)
        assert_equal(garch.q, 1)

    def test_garch_power(self):
        garch = GARCH(power=1.0)
        assert_equal(garch.num_params, 3)
        assert_equal(garch.name, 'AVGARCH')
        assert_equal(garch.power, 1.0)

        sv = garch.starting_values(self.resids)
        assert_equal(sv.shape[0], garch.num_params)

        bounds = garch.bounds(self.resids)
        assert_equal(bounds[0], (0.0, 10.0 * np.mean(np.abs(self.resids))))
        assert_equal(bounds[1], (0.0, 1.0))
        assert_equal(bounds[2], (0.0, 1.0))
        var_bounds = garch.variance_bounds(self.resids)
        backcast = garch.backcast(self.resids)
        w = 0.94 ** np.arange(75)
        assert_almost_equal(backcast,
                            np.sum(np.abs(self.resids[:75]) * (w / w.sum())))

        parameters = np.array([.1, .1, .8])
        garch.compute_variance(parameters, self.resids, self.sigma2, backcast,
                               var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        rec.garch_recursion(parameters,
                            np.abs(self.resids),
                            np.sign(self.resids),
                            cond_var_direct,
                            1, 0, 1, self.T, backcast, var_bounds)
        cond_var_direct **= 2.0  # Square since recursion does not apply power
        assert_allclose(self.sigma2, cond_var_direct)

        a, b = garch.constraints()
        a_target = np.vstack((np.eye(3), np.array([[0, -1.0, -1.0]])))
        b_target = np.array([0.0, 0.0, 0.0, -1.0])
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)
        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = garch.simulate(parameters, self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        initial_value = 1.0
        sigma = np.zeros(self.T + 500)
        data = np.zeros(self.T + 500)
        for t in range(self.T + 500):
            sigma[t] = parameters[0]
            shock = initial_value if t == 0 else np.abs(data[t - 1])
            sigma[t] += parameters[1] * shock
            lagged_value = initial_value if t == 0 else sigma[t - 1]
            sigma[t] += parameters[2] * lagged_value
            data[t] = e[t] * sigma[t]
        data = data[500:]
        sigma2 = sigma[500:] ** 2.0
        assert_almost_equal(data - sim_data[0] + 1.0, np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

    def test_arch(self):
        arch = ARCH()

        sv = arch.starting_values(self.resids)
        assert_equal(sv.shape[0], arch.num_params)

        bounds = arch.bounds(self.resids)
        assert_equal(bounds[0], (0.0, 10.0 * np.mean(self.resids ** 2.0)))
        assert_equal(bounds[1], (0.0, 1.0))

        backcast = arch.backcast(self.resids)
        w = 0.94 ** np.arange(75)
        assert_almost_equal(backcast,
                            np.sum((self.resids[:75] ** 2) * (w / w.sum())))

        parameters = np.array([0.5, 0.7])
        var_bounds = arch.variance_bounds(self.resids)
        arch.compute_variance(parameters, self.resids, self.sigma2, backcast,
                              var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        rec.arch_recursion(parameters, self.resids, cond_var_direct, 1,
                           self.T, backcast, var_bounds)
        assert_allclose(self.sigma2, cond_var_direct)

        a, b = arch.constraints()
        a_target = np.vstack((np.eye(2), np.array([[0, -1.0]])))
        b_target = np.array([0.0, 0.0, -1.0])
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)
        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = arch.simulate(parameters, self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        initial_value = 1.0
        sigma2 = np.zeros(self.T + 500)
        data = np.zeros(self.T + 500)
        for t in range(self.T + 500):
            sigma2[t] = parameters[0]
            shock = initial_value if t == 0 else data[t - 1] ** 2.0
            sigma2[t] += parameters[1] * shock
            data[t] = e[t] * np.sqrt(sigma2[t])
        data = data[500:]
        sigma2 = sigma2[500:]
        assert_almost_equal(data - sim_data[0] + 1.0, np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

        names = arch.parameter_names()
        names_target = ['omega', 'alpha[1]']
        assert_equal(names, names_target)

        assert_equal(arch.name, 'ARCH')
        assert_equal(arch.num_params, 2)
        assert_equal(arch.p, 1)
        assert isinstance(arch.__str__(), str)
        txt = arch.__repr__()
        assert str(hex(id(arch))) in txt

    def test_arch_harch(self):
        arch = ARCH(p=1)
        harch = HARCH(lags=1)
        assert_equal(arch.num_params, harch.num_params)
        parameters = np.array([0.5, 0.5])

        backcast = arch.backcast(self.resids)
        assert_equal(backcast, harch.backcast(self.resids))
        sigma2_arch = np.zeros_like(self.sigma2)
        sigma2_harch = np.zeros_like(self.sigma2)
        var_bounds = arch.variance_bounds(self.resids)
        arch.compute_variance(parameters, self.resids, sigma2_arch, backcast,
                              var_bounds)
        harch.compute_variance(parameters, self.resids, sigma2_harch, backcast,
                               var_bounds)
        assert_allclose(sigma2_arch, sigma2_harch)

        a, b = arch.constraints()
        ah, bh = harch.constraints()
        assert_equal(a, ah)
        assert_equal(b, bh)
        assert isinstance(arch.__str__(), str)
        txt = arch.__repr__()
        assert str(hex(id(arch))) in txt

    def test_harch(self):
        harch = HARCH(lags=[1, 5, 22])

        sv = harch.starting_values(self.resids)
        assert_equal(sv.shape[0], harch.num_params)

        bounds = harch.bounds(self.resids)
        assert_equal(bounds[0], (0.0, 10.0 * np.mean(self.resids ** 2.0)))
        assert_equal(bounds[1], (0.0, 1.0))
        assert_equal(bounds[2], (0.0, 1.0))
        assert_equal(bounds[3], (0.0, 1.0))
        var_bounds = harch.variance_bounds(self.resids)
        backcast = harch.backcast(self.resids)
        w = 0.94 ** np.arange(75)
        assert_almost_equal(backcast,
                            np.sum((self.resids[:75] ** 2) * (w / w.sum())))

        parameters = np.array([.1, .4, .3, .2])

        var_bounds = harch.variance_bounds(self.resids)
        harch.compute_variance(parameters, self.resids, self.sigma2,
                               backcast, var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        lags = np.array([1, 5, 22], dtype=np.int32)
        rec.harch_recursion(parameters,
                            self.resids,
                            cond_var_direct,
                            lags,
                            self.T,
                            backcast,
                            var_bounds)

        names = harch.parameter_names()
        names_target = ['omega', 'alpha[1]', 'alpha[5]', 'alpha[22]']
        assert_equal(names, names_target)

        assert_allclose(self.sigma2, cond_var_direct)

        a, b = harch.constraints()
        a_target = np.vstack((np.eye(4), np.array([[0, -1.0, -1.0, -1.0]])))
        b_target = np.array([0.0, 0.0, 0.0, 0.0, -1.0])
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)
        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = harch.simulate(parameters, self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        sigma2 = np.zeros(self.T + 500)
        data = np.zeros(self.T + 500)
        lagged = np.zeros(22)
        for t in range(self.T + 500):
            sigma2[t] = parameters[0]
            lagged[:] = backcast
            if t > 0:
                if t == 1:
                    lagged[0] = data[0] ** 2.0
                elif t < 22:
                    lagged[:t] = data[t - 1::-1] ** 2.0
                else:
                    lagged = data[t - 1:t - 22:-1] ** 2.0

            shock1 = data[t - 1] ** 2.0 if t > 0 else backcast
            if t >= 5:
                shock5 = np.mean(data[t - 5:t] ** 2.0)
            else:
                shock5 = 0.0
                for i in range(5):
                    shock5 += data[t - i - 1] if t - i - 1 >= 0 else backcast
                shock5 = shock5 / 5.0

            if t >= 22:
                shock22 = np.mean(data[t - 22:t] ** 2.0)
            else:
                shock22 = 0.0
                for i in range(22):
                    shock22 += data[t - i - 1] if t - i - 1 >= 0 else backcast
                shock22 = shock22 / 22.0

            sigma2[t] += parameters[1] * shock1 + parameters[2] * shock5 + parameters[3] * shock22

            data[t] = e[t] * np.sqrt(sigma2[t])
        data = data[500:]
        sigma2 = sigma2[500:]
        assert_almost_equal(data - sim_data[0] + 1.0, np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

        assert_equal(harch.name, 'HARCH')
        assert_equal(harch.lags, [1, 5, 22])
        assert_equal(harch.num_params, 4)
        assert isinstance(harch.__str__(), str)
        txt = harch.__repr__()
        assert str(hex(id(harch))) in txt

    def test_constant_variance(self):
        cv = ConstantVariance()

        sv = cv.starting_values(self.resids)
        assert_equal(sv.shape[0], cv.num_params)

        bounds = cv.bounds(self.resids)
        mean_square = np.mean(self.resids ** 2.0)
        assert_almost_equal(bounds[0],
                            (self.resid_var / 100000.0, 10.0 * mean_square))

        backcast = cv.backcast(self.resids)
        var_bounds = cv.variance_bounds(self.resids)
        assert_almost_equal(self.resid_var, backcast)

        parameters = np.array([self.resid_var])

        cv.compute_variance(parameters, self.resids, self.sigma2, backcast,
                            var_bounds)
        assert_allclose(np.ones_like(self.sigma2) * self.resid_var,
                        self.sigma2)

        a, b = cv.constraints()
        a_target = np.eye(1)
        b_target = np.array([0.0])
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)

        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = cv.simulate(parameters, self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        sigma2 = np.zeros(self.T + 500)
        sigma2[:] = parameters[0]
        data = np.zeros(self.T + 500)
        data[:] = np.sqrt(sigma2) * e
        data = data[500:]
        sigma2 = sigma2[500:]

        names = cv.parameter_names()
        names_target = ['sigma2']
        assert_equal(names, names_target)

        assert_almost_equal(data - sim_data[0] + 1.0, np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

        assert_equal(cv.num_params, 1)
        assert_equal(cv.name, 'Constant Variance')
        assert isinstance(cv.__str__(), str)
        txt = cv.__repr__()
        assert str(hex(id(cv))) in txt

    def test_garch_no_symmetric(self):
        garch = GARCH(p=0, o=1, q=1)

        sv = garch.starting_values(self.resids)
        assert_equal(sv.shape[0], garch.num_params)

        bounds = garch.bounds(self.resids)
        assert_equal(bounds[0], (0.0, 10.0 * np.mean(self.resids ** 2.0)))
        assert_equal(bounds[1], (0.0, 2.0))
        assert_equal(bounds[2], (0.0, 1.0))
        var_bounds = garch.variance_bounds(self.resids)
        backcast = garch.backcast(self.resids)
        parameters = np.array([.1, .1, .8])

        names = garch.parameter_names()
        names_target = ['omega', 'gamma[1]', 'beta[1]']
        assert_equal(names, names_target)

        garch.compute_variance(parameters, self.resids, self.sigma2,
                               backcast, var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        rec.garch_recursion(parameters,
                            self.resids ** 2.0,
                            np.sign(self.resids),
                            cond_var_direct,
                            0, 1, 1, self.T, backcast, var_bounds)
        assert_allclose(self.sigma2, cond_var_direct)

        a, b = garch.constraints()
        a_target = np.vstack((np.eye(3), np.array([[0, -0.5, -1.0]])))
        b_target = np.array([0.0, 0.0, 0.0, -1.0])
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)
        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = garch.simulate(parameters, self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        initial_value = 1.0
        sigma2 = np.zeros(self.T + 500)
        data = np.zeros(self.T + 500)
        for t in range(self.T + 500):
            sigma2[t] = parameters[0]
            shock = 0.5 * initial_value if t == 0 else \
                data[t - 1] ** 2.0 * (data[t - 1] < 0)
            sigma2[t] += parameters[1] * shock
            lagged_value = initial_value if t == 0 else sigma2[t - 1]
            sigma2[t] += parameters[2] * lagged_value
            data[t] = e[t] * np.sqrt(sigma2[t])
        data = data[500:]
        sigma2 = sigma2[500:]
        assert_almost_equal(data - sim_data[0] + 1.0, np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

        assert_equal(garch.p, 0)
        assert_equal(garch.o, 1)
        assert_equal(garch.q, 1)
        assert_equal(garch.num_params, 3)
        assert_equal(garch.name, 'GJR-GARCH')

    def test_garch_no_lagged_vol(self):
        garch = GARCH(p=1, o=1, q=0)
        sv = garch.starting_values(self.resids)
        assert_equal(sv.shape[0], garch.num_params)

        bounds = garch.bounds(self.resids)
        assert_equal(bounds[0], (0.0, 10.0 * np.mean(self.resids ** 2.0)))
        assert_equal(bounds[1], (0.0, 1.0))
        assert_equal(bounds[2], (-1.0, 2.0))

        backcast = garch.backcast(self.resids)
        parameters = np.array([.5, .25, .5])
        var_bounds = garch.variance_bounds(self.resids)

        garch.compute_variance(parameters, self.resids, self.sigma2,
                               backcast, var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        rec.garch_recursion(parameters,
                            self.resids ** 2.0,
                            np.sign(self.resids),
                            cond_var_direct,
                            1, 1, 0, self.T, backcast, var_bounds)
        assert_allclose(self.sigma2, cond_var_direct)

        a, b = garch.constraints()
        a_target = np.vstack((np.eye(3), np.array([[0, -1.0, -0.5]])))
        a_target[2, 1] = 1.0
        b_target = np.array([0.0, 0.0, 0.0, -1.0])
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)
        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = garch.simulate(parameters, self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        initial_value = 1.0
        sigma2 = np.zeros(self.T + 500)
        data = np.zeros(self.T + 500)
        for t in range(self.T + 500):
            sigma2[t] = parameters[0]
            shock = initial_value if t == 0 else data[t - 1] ** 2.0
            sigma2[t] += parameters[1] * shock
            shock = 0.5 * initial_value if t == 0 else \
                (data[t - 1] ** 2.0) * (data[t - 1] < 0)
            sigma2[t] += parameters[2] * shock
            data[t] = e[t] * np.sqrt(sigma2[t])
        data = data[500:]
        sigma2 = sigma2[500:]
        assert_almost_equal(data - sim_data[0] + 1.0, np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

        assert_equal(garch.p, 1)
        assert_equal(garch.o, 1)
        assert_equal(garch.q, 0)
        assert_equal(garch.num_params, 3)
        assert_equal(garch.name, 'GJR-GARCH')

    def test_arch_multiple_lags(self):
        arch = ARCH(p=5)

        sv = arch.starting_values(self.resids)
        assert_equal(sv.shape[0], arch.num_params)

        bounds = arch.bounds(self.resids)
        assert_equal(bounds[0], (0.0, 10.0 * np.mean(self.resids ** 2.0)))
        for i in range(1, 6):
            assert_equal(bounds[i], (0.0, 1.0))
        var_bounds = arch.variance_bounds(self.resids)
        backcast = arch.backcast(self.resids)
        parameters = np.array([0.25, 0.17, 0.16, 0.15, 0.14, 0.13])
        arch.compute_variance(parameters, self.resids, self.sigma2, backcast,
                              var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        rec.arch_recursion(parameters, self.resids, cond_var_direct, 5,
                           self.T, backcast, var_bounds)
        assert_allclose(self.sigma2, cond_var_direct)

        a, b = arch.constraints()
        a_target = np.vstack((np.eye(6),
                              np.array([[0, -1.0, -1.0, -1.0, -1.0, -1.0]])))
        b_target = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0])
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)
        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = arch.simulate(parameters, self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        initial_value = 1.0
        sigma2 = np.zeros(self.T + 500)
        data = np.zeros(self.T + 500)
        for t in range(self.T + 500):
            sigma2[t] = parameters[0]
            for i in range(5):
                if t - i - 1 < 0:
                    sigma2[t] += parameters[i + 1] * initial_value
                else:
                    sigma2[t] += parameters[i + 1] * data[t - i - 1] ** 2.0
            data[t] = e[t] * np.sqrt(sigma2[t])
        data = data[500:]
        sigma2 = sigma2[500:]
        assert_almost_equal(data - sim_data[0] + 1.0, np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

        names = arch.parameter_names()
        names_target = ['omega']
        names_target.extend(['alpha[' + str(i + 1) + ']' for i in range(5)])
        assert_equal(names, names_target)

        assert_equal(arch.num_params, 6)
        assert_equal(arch.name, 'ARCH')

    def test_harch_scalar(self):
        harch = HARCH(lags=2)
        assert_equal(harch.num_params, 3)
        assert_equal(harch.name, 'HARCH')

    def test_garch_many_lags(self):
        garch = GARCH(p=1, o=2, q=3)
        assert_equal(garch.num_params, 7)
        assert_equal(garch.name, 'GJR-GARCH')

        names = garch.parameter_names()
        names_target = ['omega', 'alpha[1]', 'gamma[1]', 'gamma[2]',
                        'beta[1]', 'beta[2]', 'beta[3]']
        assert_equal(names, names_target)

    def test_errors(self):
        with pytest.raises(ValueError):
            GARCH(p=-1)
        with pytest.raises(ValueError):
            GARCH(o=-1)
        with pytest.raises(ValueError):
            GARCH(q=-1)
        with pytest.raises(ValueError):
            GARCH(p=0, q=0)
        with pytest.raises(ValueError):
            GARCH(power=-0.5)
        with pytest.raises(ValueError):
            EWMAVariance(lam=-0.5)
        with pytest.raises(ValueError):
            RiskMetrics2006(tau0=1, tau1=10)
        with pytest.raises(ValueError):
            RiskMetrics2006(tau0=1, tau1=10)
        with pytest.raises(ValueError):
            RiskMetrics2006(tau1=-10)
        with pytest.raises(ValueError):
            RiskMetrics2006(tau0=10, tau1=8, rho=1.5)
        with pytest.raises(ValueError):
            RiskMetrics2006(kmax=0)
        with pytest.raises(ValueError):
            RiskMetrics2006(rho=0.5)

    @pytest.mark.skipif(not PY3, reason='Repeated warnings are incorrectly processed by pytest')
    def test_warnings_nonstationary(self):
        garch = GARCH()
        parameters = np.array([0.1, 0.2, 0.8, 4.0])
        studt = StudentsT()
        warnings.simplefilter('always', UserWarning)
        with pytest.warns(InitialValueWarning):
            garch.simulate(parameters, 1000, studt.simulate([4.0]))

    @pytest.mark.skipif(not PY3, reason='Repeated warnings are incorrectly processed by pytest')
    def test_warnings_nonstationary_garch(self):
        garch = GARCH()
        parameters = np.array([0.1, 0.2, 0.8, 4.0, 0.5])
        skewstud = SkewStudent()
        with pytest.warns(InitialValueWarning):
            garch.simulate(parameters, 1000, skewstud.simulate([4.0, 0.5]))

    @pytest.mark.skipif(not PY3, reason='Repeated warnings are incorrectly processed by pytest')
    def test_warnings_nonstationary_harch(self):
        studt = StudentsT()
        harch = HARCH(lags=[1, 5, 22])
        parameters = np.array([0.1, 0.2, 0.4, 0.5])
        with pytest.warns(InitialValueWarning):
            harch.simulate(parameters, 1000, studt.simulate([4.0]))

    def test_model_names(self):
        garch = GARCH(2, 0, 0)
        assert_equal(garch.name, 'ARCH')
        garch = GARCH(2, 0, 2)
        assert_equal(garch.name, 'GARCH')
        garch = GARCH(2, 2, 2)
        assert_equal(garch.name, 'GJR-GARCH')
        garch = GARCH(1, 0, 0, power=1.0)
        assert_equal(garch.name, 'AVARCH')
        garch = GARCH(1, 0, 1, power=1.0)
        assert_equal(garch.name, 'AVGARCH')
        garch = GARCH(1, 1, 1, power=1.0)
        assert_equal(garch.name, 'TARCH/ZARCH')
        garch = GARCH(3, 0, 0, power=1.5)
        assert_equal(garch.name, 'Power ARCH (power: 1.5)')
        assert 'Power' in garch.__str__()
        garch = GARCH(1, 2, 1, power=1.5)
        assert_equal(garch.name, 'Asym. Power GARCH (power: 1.5)')
        garch = GARCH(2, 0, 2, power=1.5)
        assert_equal(garch.name, 'Power GARCH (power: 1.5)')

    def test_ewma(self):
        ewma = EWMAVariance()

        sv = ewma.starting_values(self.resids)
        assert_equal(sv.shape[0], ewma.num_params)

        bounds = ewma.bounds(self.resids)
        assert_equal(len(bounds), 0)
        var_bounds = ewma.variance_bounds(self.resids)
        backcast = ewma.backcast(self.resids)
        parameters = np.array([])

        names = ewma.parameter_names()
        names_target = []
        assert_equal(names, names_target)

        ewma.compute_variance(parameters, self.resids, self.sigma2,
                              backcast, var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        parameters = np.array([0.0, 0.06, 0.94])
        rec.garch_recursion(parameters,
                            self.resids ** 2.0,
                            np.sign(self.resids),
                            cond_var_direct,
                            1, 0, 1, self.T, backcast, var_bounds)

        assert_allclose(self.sigma2 / cond_var_direct,
                        np.ones_like(self.sigma2))

        a, b = ewma.constraints()
        a_target = np.empty((0, 0))
        b_target = np.empty((0,))
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)
        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = ewma.simulate(parameters, self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        initial_value = 1.0

        sigma2 = np.zeros(self.T + 500)
        data = np.zeros(self.T + 500)
        sigma2[0] = initial_value
        data[0] = np.sqrt(initial_value)
        for t in range(1, self.T + 500):
            sigma2[t] = 0.94 * sigma2[t - 1] + 0.06 * data[t - 1] ** 2.0
            data[t] = e[t] * np.sqrt(sigma2[t])

        data = data[500:]
        sigma2 = sigma2[500:]
        assert_almost_equal(data - sim_data[0] + 1.0, np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

        assert_equal(ewma.num_params, 0)
        assert_equal(ewma.name, 'EWMA/RiskMetrics')
        assert isinstance(ewma.__str__(), str)
        txt = ewma.__repr__()
        assert str(hex(id(ewma))) in txt

    def test_ewma_estimated(self):
        ewma = EWMAVariance(lam=None)

        sv = ewma.starting_values(self.resids)
        assert sv == 0.94
        assert sv.shape[0] == ewma.num_params

        bounds = ewma.bounds(self.resids)
        assert len(bounds) == 1
        assert bounds == [(0, 1)]

        ewma.variance_bounds(self.resids)

        backcast = ewma.backcast(self.resids)
        w = 0.94 ** np.arange(75)
        assert_almost_equal(backcast,
                            np.sum((self.resids[:75] ** 2) * (w / w.sum())))

        parameters = np.array([0.9234])

        var_bounds = ewma.variance_bounds(self.resids)
        ewma.compute_variance(parameters, self.resids, self.sigma2, backcast, var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        cond_var_direct[0] = backcast
        parameters = np.array([0, 1 - parameters[0], parameters[0]])
        rec.garch_recursion(parameters,
                            self.resids ** 2.0,
                            np.sign(self.resids),
                            cond_var_direct,
                            1, 0, 1, self.T, backcast, var_bounds)
        assert_allclose(self.sigma2, cond_var_direct)
        assert_allclose(self.sigma2 / cond_var_direct, np.ones_like(self.sigma2))

        names = ewma.parameter_names()
        names_target = ['lam']
        assert_equal(names, names_target)

        a, b = ewma.constraints()
        a_target = np.ones((1, 1))
        b_target = np.zeros((1,))
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)

        assert_equal(ewma.num_params, 1)
        assert_equal(ewma.name, 'EWMA/RiskMetrics')
        assert isinstance(ewma.__str__(), str)
        txt = ewma.__repr__()
        assert str(hex(id(ewma))) in txt

        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        lam = parameters[-1]
        sim_data = ewma.simulate([lam], self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        initial_value = 1.0

        sigma2 = np.zeros(self.T + 500)
        data = np.zeros(self.T + 500)
        sigma2[0] = initial_value
        data[0] = np.sqrt(initial_value)
        for t in range(1, self.T + 500):
            sigma2[t] = lam * sigma2[t - 1] + (1-lam) * data[t - 1] ** 2.0
            data[t] = e[t] * np.sqrt(sigma2[t])

        data = data[500:]
        sigma2 = sigma2[500:]
        assert_almost_equal(data - sim_data[0] + 1.0, np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

    def test_riskmetrics(self):
        rm06 = RiskMetrics2006()

        sv = rm06.starting_values(self.resids)
        assert_equal(sv.shape[0], rm06.num_params)

        bounds = rm06.bounds(self.resids)
        assert_equal(len(bounds), 0)
        var_bounds = rm06.variance_bounds(self.resids)
        backcast = rm06.backcast(self.resids)
        assert_equal(backcast.shape[0], 14)
        parameters = np.array([])

        names = rm06.parameter_names()
        names_target = []
        assert_equal(names, names_target)

        # TODO: Test variance fit by RM06
        rm06.compute_variance(parameters, self.resids, self.sigma2,
                              backcast, var_bounds)

        a, b = rm06.constraints()
        a_target = np.empty((0, 0))
        b_target = np.empty((0,))
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)

        # TODO: Test RM06 Simulation
        state = self.rng.get_state()
        assert isinstance(state, tuple)
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = rm06.simulate(parameters, self.T, rng.simulate([]))
        assert isinstance(sim_data, tuple)
        assert len(sim_data) == 2
        assert isinstance(sim_data[0], np.ndarray)
        assert isinstance(sim_data[1], np.ndarray)

        assert_equal(rm06.num_params, 0)
        assert_equal(rm06.name, 'RiskMetrics2006')

    def test_egarch(self):
        egarch = EGARCH(p=1, o=1, q=1)

        sv = egarch.starting_values(self.resids)
        assert_equal(sv.shape[0], egarch.num_params)

        bounds = egarch.bounds(self.resids)
        assert_equal(len(bounds), egarch.num_params)
        const = np.log(10000.0)
        lnv = np.log(np.mean(self.resids ** 2.0))
        assert_equal(bounds[0], (lnv - const, lnv + const))
        assert_equal(bounds[1], (-np.inf, np.inf))
        assert_equal(bounds[2], (-np.inf, np.inf))
        assert_equal(bounds[3], (0.0, 1.0))
        backcast = egarch.backcast(self.resids)

        w = 0.94 ** np.arange(75)
        backcast_test = np.sum((self.resids[:75] ** 2) * (w / w.sum()))
        assert_almost_equal(backcast, np.log(backcast_test))

        var_bounds = egarch.variance_bounds(self.resids)
        parameters = np.array([.1, .1, -.1, .95])
        egarch.compute_variance(parameters, self.resids, self.sigma2, backcast,
                                var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        lnsigma2 = np.empty(self.T)
        std_resids = np.empty(self.T)
        abs_std_resids = np.empty(self.T)
        rec.egarch_recursion(parameters, self.resids, cond_var_direct, 1, 1, 1,
                             self.T, backcast, var_bounds, lnsigma2,
                             std_resids, abs_std_resids)
        assert_allclose(self.sigma2, cond_var_direct)

        a, b = egarch.constraints()
        a_target = np.vstack((np.array([[0, 0, 0, -1.0]])))
        b_target = np.array([-1.0])
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)

        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = egarch.simulate(parameters, self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        initial_value = 0.1 / (1 - 0.95)
        lnsigma2 = np.zeros(self.T + 500)
        lnsigma2[0] = initial_value
        sigma2 = np.zeros(self.T + 500)
        sigma2[0] = np.exp(lnsigma2[0])
        data = np.zeros(self.T + 500)
        data[0] = np.sqrt(sigma2[0]) * e[0]
        norm_const = np.sqrt(2 / np.pi)
        for t in range(1, self.T + 500):
            lnsigma2[t] = parameters[0]
            lnsigma2[t] += parameters[1] * (np.abs(e[t - 1]) - norm_const)
            lnsigma2[t] += parameters[2] * e[t - 1]
            lnsigma2[t] += parameters[3] * lnsigma2[t - 1]

        sigma2 = np.exp(lnsigma2)
        data = e * np.sqrt(sigma2)

        data = data[500:]
        sigma2 = sigma2[500:]

        assert_almost_equal(data - sim_data[0] + 1.0, np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

        names = egarch.parameter_names()
        names_target = ['omega', 'alpha[1]', 'gamma[1]', 'beta[1]']
        assert_equal(names, names_target)
        assert_equal(egarch.name, 'EGARCH')
        assert_equal(egarch.num_params, 4)

        assert_equal(egarch.p, 1)
        assert_equal(egarch.o, 1)
        assert_equal(egarch.q, 1)
        assert isinstance(egarch.__str__(), str)
        txt = egarch.__repr__()
        assert str(hex(id(egarch))) in txt

        with pytest.raises(ValueError):
            EGARCH(p=0, o=0, q=1)
        with pytest.raises(ValueError):
            EGARCH(p=1, o=1, q=-1)
        parameters = np.array([.1, .1, -.1, 1.05])
        with pytest.warns(InitialValueWarning):
            egarch.simulate(parameters, self.T, rng.simulate([]))

    def test_egarch_100(self):
        egarch = EGARCH(p=1, o=0, q=0)

        sv = egarch.starting_values(self.resids)
        assert_equal(sv.shape[0], egarch.num_params)

        backcast = egarch.backcast(self.resids)
        w = 0.94 ** np.arange(75)
        backcast_test = np.sum((self.resids[:75] ** 2) * (w / w.sum()))
        assert_almost_equal(backcast, np.log(backcast_test))

        var_bounds = egarch.variance_bounds(self.resids)
        parameters = np.array([.1, .4])
        egarch.compute_variance(parameters, self.resids, self.sigma2, backcast,
                                var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        lnsigma2 = np.empty(self.T)
        std_resids = np.empty(self.T)
        abs_std_resids = np.empty(self.T)
        rec.egarch_recursion(parameters, self.resids, cond_var_direct, 1, 0, 0,
                             self.T, backcast, var_bounds, lnsigma2,
                             std_resids, abs_std_resids)
        assert_allclose(self.sigma2, cond_var_direct)

        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = egarch.simulate(parameters, self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        initial_value = 0.1 / (1 - 0.95)
        lnsigma2 = np.zeros(self.T + 500)
        lnsigma2[0] = initial_value
        sigma2 = np.zeros(self.T + 500)
        sigma2[0] = np.exp(lnsigma2[0])
        data = np.zeros(self.T + 500)
        data[0] = np.sqrt(sigma2[0]) * e[0]
        norm_const = np.sqrt(2 / np.pi)
        for t in range(1, self.T + 500):
            lnsigma2[t] = parameters[0]
            lnsigma2[t] += parameters[1] * (np.abs(e[t - 1]) - norm_const)

        sigma2 = np.exp(lnsigma2)
        data = e * np.sqrt(sigma2)

        data = data[500:]
        sigma2 = sigma2[500:]

        assert_almost_equal(data - sim_data[0] + 1.0, np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

    def test_fixed_variance(self):
        variance = np.arange(1000.0) + 1.0
        fv = FixedVariance(variance)
        fv.start, fv.stop = 0, 1000
        parameters = np.array([2.0])
        resids = self.resids
        sigma2 = np.empty_like(resids)
        backcast = fv.backcast(resids)
        var_bounds = fv.variance_bounds(resids, 2.0)
        fv.compute_variance(parameters, resids, sigma2, backcast, var_bounds)
        sv = fv.starting_values(resids)
        cons = fv.constraints()
        bounds = fv.bounds(resids)
        assert_allclose(sigma2, 2.0 * variance)
        assert_allclose(sv, (resids / np.sqrt(variance)).var())
        assert var_bounds.shape == (resids.shape[0], 2)
        assert fv.num_params == 1
        assert fv.parameter_names() == ['scale']
        assert fv.name == 'Fixed Variance'
        assert_equal(cons[0], np.ones((1, 1)))
        assert_equal(cons[1], np.zeros(1))
        assert_equal(bounds[0][0], sv[0] / 100000.0)

        sigma2 = np.empty(500)
        fv.start = 250
        fv.stop = 750
        fv.compute_variance(parameters, resids[250:750], sigma2, backcast, var_bounds)
        assert_allclose(sigma2, 2.0 * variance[250:750])

        fv = FixedVariance(variance, unit_scale=True)
        fv.start, fv.stop = 0, 1000
        sigma2 = np.empty_like(resids)
        parameters = np.empty(0)
        fv.compute_variance(parameters, resids, sigma2, backcast, var_bounds)
        sv = fv.starting_values(resids)
        cons = fv.constraints()
        bounds = fv.bounds(resids)

        assert_allclose(sigma2, variance)
        assert_allclose(sv, np.empty(0))
        assert fv.num_params == 0
        assert fv.parameter_names() == []
        assert fv.name == 'Fixed Variance (Unit Scale)'
        assert_equal(cons[0], np.empty((0, 0)))
        assert_equal(cons[1], np.empty((0)))
        assert bounds == []
        rng = Normal()
        with pytest.raises(NotImplementedError):
            fv.simulate(parameters, 1000, rng)

        fv = FixedVariance(variance, unit_scale=True)
        fv.start, fv.stop = 123, 731
        sigma2 = np.empty_like(resids)
        parameters = np.empty(0)
        assert fv.start == 123
        assert fv.stop == 731
        with pytest.raises(ValueError):
            fv.compute_variance(parameters, resids, sigma2, backcast, var_bounds)

    def test_midas_symmetric(self):
        midas = MIDASHyperbolic()

        sv = midas.starting_values(self.resids)
        assert_equal(sv.shape[0], midas.num_params)

        bounds = midas.bounds(self.resids)
        assert_equal(bounds[0], (0.0, 10.0 * np.mean(self.resids ** 2.0)))
        assert_equal(bounds[1], (0.0, 1.0))
        assert_equal(bounds[2], (0.0, 1.0))
        backcast = midas.backcast(self.resids)
        w = 0.94 ** np.arange(75)
        assert_almost_equal(backcast, np.sum((self.resids[:75] ** 2) * (w / w.sum())))
        var_bounds = midas.variance_bounds(self.resids)
        parameters = np.array([.1, .9, .4])
        midas.compute_variance(parameters, self.resids, self.sigma2, backcast, var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        weights = midas._weights(parameters)
        theta = parameters[-1]
        j = np.arange(1, 22 + 1)
        direct_weights = gamma(j + theta) / (gamma(j+1)*gamma(theta))
        direct_weights = direct_weights / direct_weights.sum()
        assert_allclose(weights, direct_weights)
        resids = self.resids
        direct_params = parameters.copy()
        direct_params[-1] = 0.0  # gamma, strip theta
        rec.midas_recursion_python(direct_params, weights, resids, cond_var_direct, self.T,
                                   backcast, var_bounds)
        assert_allclose(self.sigma2, cond_var_direct)

        a, b = midas.constraints()
        a_target = np.zeros((5, 3))
        a_target[0, 0] = 1
        a_target[1, 1] = 1
        a_target[2, 1] = -1
        a_target[3, 2] = 1
        a_target[4, 2] = -1
        b_target = np.array([0.0, 0.0, -1.0, 0.0, -1.0])
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)
        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        sim_data = midas.simulate(parameters, self.T, rng.simulate([]))
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + 500)
        initial_value = 1.0
        sigma2 = np.zeros(self.T + 500)
        data = np.zeros(self.T + 500)
        sigma2[:22] = initial_value
        omega, alpha = parameters[:2]
        for t in range(22, self.T + 500):
            sigma2[t] = omega
            for i in range(22):
                shock = initial_value if t - i - 1 < 22 else data[t - i - 1] ** 2.0
                sigma2[t] += alpha * weights[i] * shock
            data[t] = e[t] * np.sqrt(sigma2[t])
        data = data[500:]
        sigma2 = sigma2[500:]
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))
        assert_almost_equal(data / sim_data[0], np.ones_like(data))

        names = midas.parameter_names()
        names_target = ['omega', 'alpha', 'theta']
        assert_equal(names, names_target)

        assert isinstance(midas.__str__(), str)
        txt = midas.__repr__()
        assert str(hex(id(midas))) in txt

        assert_equal(midas.name, 'MIDAS Hyperbolic')
        assert_equal(midas.num_params, 3)
        assert_equal(midas.m, 22)

        with pytest.warns(InitialValueWarning):
            parameters = np.array([.1, 1.1, .4])
            midas.simulate(parameters, self.T, rng.simulate([]))

    def test_midas_asymmetric(self):
        midas = MIDASHyperbolic(33, asym=True)

        sv = midas.starting_values(self.resids)
        assert_equal(sv.shape[0], midas.num_params)

        bounds = midas.bounds(self.resids)
        assert_equal(bounds[0], (0.0, 10.0 * np.mean(self.resids ** 2.0)))
        assert_equal(bounds[1], (0.0, 1.0))
        assert_equal(bounds[2], (-1.0, 2.0))
        assert_equal(bounds[3], (0.0, 1.0))
        backcast = midas.backcast(self.resids)
        w = 0.94 ** np.arange(75)
        assert_almost_equal(backcast, np.sum((self.resids[:75] ** 2) * (w / w.sum())))
        var_bounds = midas.variance_bounds(self.resids)
        parameters = np.array([.1, .3, 1.2, .4])
        midas.compute_variance(parameters, self.resids, self.sigma2, backcast, var_bounds)
        cond_var_direct = np.zeros_like(self.sigma2)
        weights = midas._weights(parameters)
        wlen = len(weights)
        theta = parameters[-1]
        j = np.arange(1, wlen+1)
        direct_weights = gammaln(j + theta) - gammaln(j + 1) - gammaln(theta)
        direct_weights = np.exp(direct_weights)
        direct_weights = direct_weights/direct_weights.sum()
        assert_allclose(direct_weights, weights)
        resids = self.resids
        direct_params = parameters[:3].copy()
        rec.midas_recursion_python(direct_params, weights, resids, cond_var_direct, self.T,
                                   backcast, var_bounds)
        assert_allclose(self.sigma2, cond_var_direct)

        a, b = midas.constraints()
        a_target = np.zeros((5, 4))
        a_target[0, 0] = 1
        a_target[1, 1] = 1
        a_target[1, 2] = 1
        a_target[2, 1] = -1
        a_target[2, 2] = -0.5
        a_target[3, 3] = 1
        a_target[4, 3] = -1
        b_target = np.array([0.0, 0.0, -1.0, 0.0, -1.0])
        assert_array_equal(a, a_target)
        assert_array_equal(b, b_target)
        state = self.rng.get_state()
        rng = Normal()
        rng.random_state.set_state(state)
        burn = wlen
        sim_data = midas.simulate(parameters, self.T, rng.simulate([]), burn=burn)
        self.rng.set_state(state)
        e = self.rng.standard_normal(self.T + burn)
        initial_value = 1.0
        sigma2 = np.zeros(self.T + burn)
        data = np.zeros(self.T + burn)
        sigma2[:wlen] = initial_value
        omega, alpha, gamma = parameters[:3]
        for t in range(wlen, self.T + burn):
            sigma2[t] = omega
            for i in range(wlen):
                if t - i - 1 < wlen:
                    shock = initial_value
                    coeff = (alpha + 0.5 * gamma) * weights[i]
                else:
                    shock = data[t - i - 1] ** 2.0
                    coeff = (alpha + gamma * (data[t - i - 1] < 0)) * weights[i]
                sigma2[t] += coeff * shock
            data[t] = e[t] * np.sqrt(sigma2[t])
        data = data[burn:]
        sigma2 = sigma2[burn:]
        assert_almost_equal(data / sim_data[0], np.ones_like(data))
        assert_almost_equal(sigma2 / sim_data[1], np.ones_like(sigma2))

        names = midas.parameter_names()
        names_target = ['omega', 'alpha', 'gamma', 'theta']
        assert_equal(names, names_target)

        assert isinstance(midas.__str__(), str)
        txt = midas.__repr__()
        assert str(hex(id(midas))) in txt

        assert_equal(midas.name, 'MIDAS Hyperbolic')
        assert_equal(midas.num_params, 4)
        assert_equal(midas.m, 33)

        with pytest.warns(InitialValueWarning):
            parameters = np.array([.1, .3, 1.6, .4])
            midas.simulate(parameters, self.T, rng.simulate([]))