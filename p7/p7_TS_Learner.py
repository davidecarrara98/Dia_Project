from p3.p3_Learner import *
from p4.p4_SplitTable import *


class TS_Learner7(Learner):
    def __init__(self, n_arms, n_features=2, names=None, rw_coef=1, conf_coef=50):
        super().__init__(n_arms)
        self.beta_parameters = np.ones((n_arms, 2))
        self.table = SplitTable(n_arms, n_classes=n_features * 2, names=names)
        self.names = names
        self.rw_coef = rw_coef
        self.conf_coef = conf_coef

    def pull_arm(self, margins):
        #intermediate
        intermediate = np.zeros(shape=self.poisson_vector.shape[0])
        for index in range(self.poisson_vector.shape[0]):
            if self.poisson_vector[index, 0] == 0 and np.sum(self.poisson_vector[:, 0]) != 0:
                intermediate[index] = np.average(self.poisson_vector[:, 0], weights=self.poisson_vector[:, 1])
        #means = intermediate[:] + np.ones(shape=self.poisson_vector.shape[0])
        means = self.poisson_vector[:, 0] + np.ones(shape=self.poisson_vector.shape[0])
        extractions = np.random.beta(self.beta_parameters[:, 0], self.beta_parameters[:, 1])
        idx = np.nanargmax(extractions * np.array(margins) * means)
        return idx

    def update(self, pulled_arm, successes, n_trials):
        self.t += 1
        # self.update_observations(pulled_arm, successes, _margin)
        self.beta_parameters[pulled_arm, 0] = self.beta_parameters[pulled_arm, 0] + successes
        self.beta_parameters[pulled_arm, 1] = self.beta_parameters[pulled_arm, 1] + n_trials - successes

    def inherit(self, ts_parent, feature, side):
        # self.names = ts_parent.names
        la = None
        if ts_parent.table.n_classes == 4 and feature == 0:
            la = [side, side + 2]
        if ts_parent.table.n_classes == 4 and feature == 1:
            la = [2 * side, (2 * side) + 1]
        if ts_parent.table.n_classes == 2:
            la = side
        if isinstance(la, int):
            self.beta_parameters[:, 0] += ts_parent.table.matrix[:, la, 1]
            self.beta_parameters[:, 1] += ts_parent.table.matrix[:, la, 0] - ts_parent.table.matrix[:, la, 1]
        else:
            self.beta_parameters[:, 0] += np.sum(ts_parent.table.matrix[:, la, 1], axis=1)
            self.beta_parameters[:, 1] += np.sum(ts_parent.table.matrix[:, la, 0], axis=1) - np.sum(
                ts_parent.table.matrix[:, la, 1], axis=1)

        for arm in range(self.n_arms):
            try:
                if isinstance(la, int):
                    self.poisson_vector[arm, 0] = ts_parent.table.matrix[arm, la, 2] / \
                                                  ts_parent.table.matrix[arm, la, 1]
                    self.poisson_vector[arm, 1] = ts_parent.table.matrix[arm, la, 1]
                else:
                    self.poisson_vector[arm, 0] = np.sum(ts_parent.table.matrix[arm, la, 2], axis=0) / \
                                                  np.sum(ts_parent.table.matrix[arm, la, 1], axis=0)
                    self.poisson_vector[arm, 1] = np.sum(ts_parent.table.matrix[arm, la, 1], axis=0)
            except FloatingPointError or ZeroDivisionError:
                self.poisson_vector[arm] = np.zeros(shape=2)
        self.table.matrix = ts_parent.table.matrix[:, la, :]

    def evaluate_means(self, margins, confidence=0.95, chosen_arms=None, list_acc=None):
        new_m = self.table.matrix
        shape = new_m.shape
        if self.table.n_classes == 4:
            new_m = np.zeros(shape=(shape[0], int(self.table.n_classes / 2), 2, 3))
            shape = new_m.shape
            new_m_accesses = np.zeros(shape=(int(self.table.n_classes / 2), 2))
            new_m_accesses[0, 0] = list_acc[0] + list_acc[2]
            new_m_accesses[0, 1] = list_acc[1] + list_acc[3]
            new_m_accesses[1, 0] = list_acc[0] + list_acc[1]
            new_m_accesses[1, 1] = list_acc[2] + list_acc[3]
            new_m[:, 0, 0, :] = self.table.matrix[:, 0, :] + self.table.matrix[:, 2, :]
            new_m[:, 0, 1, :] = self.table.matrix[:, 1, :] + self.table.matrix[:, 3, :]
            new_m[:, 1, 0, :] = self.table.matrix[:, 0, :] + self.table.matrix[:, 1, :]
            new_m[:, 1, 1, :] = self.table.matrix[:, 2, :] + self.table.matrix[:, 3, :]
        if self.table.n_classes == 2:
            new_m = np.zeros(shape=(shape[0], int(self.table.n_classes / 2), 2, 3))
            shape = new_m.shape
            new_m_accesses = np.zeros(shape=(int(self.table.n_classes / 2), 2))
            new_m_accesses[0, 0] = list_acc[0]
            new_m_accesses[0, 1] = list_acc[1]
            new_m[:, 0, 0, :] = self.table.matrix[:, 0, :]
            new_m[:, 0, 1, :] = self.table.matrix[:, 1, :]

        if chosen_arms is None:
            chosen_arms = range(self.table.matrix.shape[0])
        else:
            chosen_arms = np.unique(np.array(chosen_arms))
        # trovare reward ottima split1
        split_reward = np.zeros(shape=(int(self.table.n_classes / 2) + 1))
        arg_list = []
        for feature in range(shape[1]):
            conf = np.zeros(shape=(shape[0]))
            for armax in chosen_arms:
                try:
                    conf[armax] = self.conf_coef * np.sqrt(-np.log(confidence) / (2 * (new_m[armax, feature, 0, 0]
                                                                                            + new_m[
                                                                                                armax, feature, 1, 0])))
                except FloatingPointError:
                    conf[armax] = 50

            mu_vec = np.zeros(shape=(shape[0], shape[2]))
            for armax in chosen_arms:
                try:
                    mu_vec[armax, 0] += new_m[armax, feature, 0, 1] / new_m[
                        armax, feature, 0, 0] * np.array(margins)[armax] * ((new_m[armax, feature, 0, 2] /
                                                                             new_m[armax, feature, 0, 1]) + 1)
                    mu_vec[armax, 0] -= conf[armax]

                except FloatingPointError:
                    mu_vec[armax, 0] = 0
                    #print('ALLARME')

                try:
                    mu_vec[armax, 1] += new_m[armax, feature, 1, 1] / new_m[
                        armax, feature, 1, 0] * np.array(margins)[armax] \
                                        * ((new_m[armax, feature, 1, 2] /
                                            new_m[armax, feature, 1, 1]) + 1)
                    mu_vec[armax, 1] -= conf[armax]

                except FloatingPointError:
                    mu_vec[armax, 1] = 0
                    #print('ALLARME')

            argopt0, argopt1 = np.argmax(mu_vec[:, 0]), np.argmax(mu_vec[:, 1])
            opt0, opt1 = np.max(mu_vec[:, 0]), np.max(mu_vec[:, 1])

            confpc = np.sqrt(-np.log(confidence) / (2 * (np.sum(new_m[:, feature, 0, 0]
                                                                + new_m[:, feature, 1, 0]))))
            pc0 = new_m_accesses[feature, 0] / (new_m_accesses[feature, 0]
                                                + new_m_accesses[feature, 1])
            pc1 = new_m_accesses[feature, 1] / (new_m_accesses[feature, 0]
                                                + new_m_accesses[feature, 1])
            pc0 -= confpc
            pc1 -= confpc
            rw = pc0 * opt0 + pc1 * opt1
            split_reward[feature] = rw
            arg_list.append([argopt0, argopt1])

        # aggregate
        average = np.zeros(shape=(new_m.shape[0], 3))
        average += np.sum(self.table.matrix, axis=1)
        rw_vec = np.zeros(shape=new_m.shape[0])
        for armax in chosen_arms:
            try:
                rw_vec[armax] = (average[armax, 1] / average[armax, 0]) * np.array(margins)[armax] * (
                            (average[armax, 2] / average[armax, 1]) + 1)
            except FloatingPointError:
                rw_vec[armax] = 0
        arg_list.append([np.argmax(rw_vec)])
        rw = np.max(rw_vec)
        split_reward[new_m.shape[1]] = self.rw_coef * rw

        # confronti
        return np.argmax(split_reward), arg_list[np.argmax(split_reward)]
