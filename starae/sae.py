# -*- coding: utf-8 -*-
# Author: Junbo (Jake) Zhao

from __future__ import division

import os
import numpy as np
from time import time

from .utils import *
from .ae import AutoEncoder


class SparseAE(AutoEncoder):
    """docstring for SparseAE"""
    def __init__(self, input_size, hidden_size, acti_fun='sigmoid',
                 optimize_method='sgd', max_iter=1000, tol=1.e-3, alpha=0.1,
                 mini_batch=0, adastep=False, momentum=False,
                 momen_beta=0.95, dpark_enable=False, dpark_run='process',
                 dpark_threads='-p 4', debug=False, lamb=0.0001,
                 rho=0.01, sparse_beta=3, verbose=False, logger=''):
        super(SparseAE, self).__init__(input_size=input_size,
                                       hidden_size=hidden_size,
                                       acti_fun=acti_fun,
                                       optimize_method=optimize_method,
                                       max_iter=max_iter,
                                       tol=tol, alpha=alpha,
                                       mini_batch=mini_batch,
                                       adastep=adastep,
                                       momentum=momentum,
                                       momen_beta=momen_beta,
                                       dpark_enable=dpark_enable,
                                       dpark_run=dpark_run,
                                       dpark_threads=dpark_threads,
                                       debug=debug, verbose=verbose,
                                       logger=logger)
        super(SparseAE, self).init_param()
        self.lamb = lamb
        self.rho = rho
        self.sparse_beta = sparse_beta
        # Debug mode, when needed.
        '''
        if self.debug:
            self.sparse_beta = 0
            self.lamb = 0
        '''

    def compute_cost(self, theta, X, epoch_flag=1, time_flag=1):  # TODO ugly.
        """SparseAE lost function"""
        # safeguard
        assert isinstance(X, np.ndarray)
        assert X.shape[0] == self.input_size
        assert self.theta.shape == theta.shape
        self.theta = theta  # Update
        # Start go forward
        cost = 0
        # TODO
        '''
        if self.dpark_enable:
            # TODO
            print 'Dpark enabled.'
        '''
        # Vectorized solution
        self.feed_forward(X)
        rho_ = np.sum(self.a2, axis=1).reshape(self.a2.shape[0], 1)
        cost += np.power(np.linalg.norm(self.a3 - self.a1), 2) / 2
        cost, rho_ = cost / X.shape[1], rho_ / X.shape[1]
        # KL penalty
        KL_penalty = self.rho * np.log(self.rho / rho_) +\
            (1 - self.rho) * np.log((1 - self.rho) / (1 - rho_))
        cost += self.sparse_beta * np.sum(KL_penalty)
        # weight decay
        cost += self.lamb / 2 * (np.linalg.norm(self.w1) ** 2 +
                                 np.linalg.norm(self.w2) ** 2)
        # TODO should be moved to optim module
        if self.verbose and not self.debug:  # TODO sooooo ugly..
            if time_flag:
                print 'cost is: %f' % cost
                # Timer logger.
                if not os.path.isdir('log/timer'):
                    os.mkdir('log/timer')
                timer2 = time()
                # global time
                g_time = timer2 - self.timer
                # record cost reducing
                self.logger = self.logger.partition('.')[0]
                with open(os.path.join('log/timer', self.logger+'.csv'),
                          'a') as flog:
                    flog.write('{0:.3f},{1:.3f}\n'.format(g_time, cost))
                # record weigths
                if not os.path.isdir(os.path.join('log/timer', self.logger)):
                    os.mkdir(os.path.join('log/timer', self.logger))
                if g_time > self.time_stamp:
                    fname = os.path.join('log/timer', self.logger,
                                         str(self.time_stamp))
                    np.savetxt(fname, self.w1, delimiter=',')
                    self.time_stamp += 10
            if epoch_flag:
                # Epoch logger
                if not os.path.isdir('log/epoch'):
                    os.mkdir('log/epoch')
                self.logger = self.logger.partition('.')[0]
                with open(os.path.join('log/epoch', self.logger+'.csv'),
                          'a') as flog:
                    flog.write('{0:.4f}\n'.format(cost))
                # record weights
                if not os.path.isdir(os.path.join('log/epoch', self.logger)):
                    os.mkdir(os.path.join('log/epoch', self.logger))
                # Get weight file number
                fname = os.path.join('log/epoch', self.logger)
                flst = os.listdir(fname)
                if not flst:
                    fname = os.path.join(fname, '0')
                else:
                    flst = map(lambda x: int(x), flst)
                    fname = os.path.join(fname, str(max(flst)+1))
                np.savetxt(fname, self.w1, delimiter=',')

        return cost

    def compute_grad(self, theta, X):
        """Back-propagation on SparseAE"""
        # safeguard
        assert isinstance(X, np.ndarray)
        assert X.shape[0] == self.input_size
        assert self.theta.shape == theta.shape
        self.theta = theta  # Update
        # Start iterate
        self.feed_forward(X)
        rho_ = np.sum(self.a2, axis=1).reshape(self.a2.shape[0], 1)/X.shape[1]
        sigma3 = -(self.a1 - self.a3) * activate_grad(self.z3)
        if self.debug:  # Here is likely to incur Numerical issue
            import warnings
            warnings.filterwarnings('error')
            try:
                sparse_sigma = -(self.rho / rho_) + (1 - self.rho) / (1 - rho_)
            except RuntimeWarning:
                import pdb; pdb.set_trace()
        else:
            sparse_sigma = -(self.rho / rho_) + (1 - self.rho) / (1 - rho_)
        sigma2 = (np.dot(self.w2.T, sigma3) + self.sparse_beta * sparse_sigma)\
            * activate_grad(self.z2)
        # Desired gradients
        w2_grad = np.dot(sigma3, self.a2.T)
        b2_grad = np.sum(sigma3, axis=1)
        w1_grad = np.dot(sigma2, self.a1.T)
        b1_grad = np.sum(sigma2, axis=1)
        # average and weight decay
        w2_grad = w2_grad / X.shape[1] + self.lamb * self.w2
        b2_grad = b2_grad / X.shape[1]
        w1_grad = w1_grad / X.shape[1] + self.lamb * self.w1
        b1_grad = b1_grad / X.shape[1]
        # vectorize
        theta_grad = vectorize(w1_grad, w2_grad, b1_grad, b2_grad)
        return theta_grad  # vector
