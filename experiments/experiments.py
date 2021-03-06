from __future__ import print_function
from future.utils import listvalues
import pickle
import random
from os import makedirs
from os.path import isdir, exists

try:
    from gmpy2 import mpq as Fraction
except ImportError:
    from fractions import Fraction

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from scipy import stats

import sys
sys.path.insert(0, '..')
import profiles
import perpetual_rules as perpetual
import perpetual_rules
from perpetual_rules import SHORT_RULENAMES


########################################################################


rules = ["av",
         "per_pav",
         "per_equality",
         "per_quota",
         "per_nash",
         "per_reset",
         "per_unitcost",
         "per_consensus",
         "serial_dictatorship",
         "per_quota_mod"
         ]


def get_all_candidates(history):
    candidates = set()
    for prof in history:
        candidates = candidates.union(prof.cands)
    return list(candidates)


def get_all_voters(history):
    voters = set()
    for prof in history:
        voters = voters.union(prof.voters)
    return list(voters)


def calculate_statistics(profiles, support, wins, quota_compliance,
                         quota_maxdeviation, influence, winner):
    num_satisfied = len([v for v in profiles.voters
                         if winner in profiles.approval_sets[v]])

    cand_support = {c: 0 for c in profiles.cands}
    for voter in profiles.voters:
        for c in profiles.approval_sets[voter]:
            cand_support[c] += 1

    for v in profiles.voters:
        support[v] += max([cand_support[c]
                           for c in profiles.approval_sets[v]] + [0])

        if winner in profiles.approval_sets[v]:
            wins[v] += 1
            influence[v] += Fraction(1, num_satisfied)
        per_quota = Fraction(support[v], len(profiles.voters))
        if per_quota - wins[v] < 1:
            quota_compliance[v] += 1
        quota_maxdeviation[v] = max(quota_maxdeviation[v],
                                    per_quota - wins[v])


# calculate the Gini coefficient
def calculate_gini(x):
    n = len(x)
    x = np.sort(x, axis=None)
    gini = (np.sum([(2 * i - n + 1) * x[i]
                    for i in range(n)], dtype=float)
            / n / sum(x))
    return gini


def plot_data(exp_name, aver_quotacompl, max_quotadeviation,
              aver_satisfaction, aver_influencegini, rules):
    def generate_boxplot(data, bottom, top, name):
            pos = [0.06 + 0.11 * i for i in range(len(rules))]
            plt.boxplot([data[rule] for rule in rules],
                        widths=0.08,
                        positions=pos,
                        whis=10**10)
            # ax.set_aspect(5)
            plt.ylim(bottom - .01, top + .01)
            plt.xlim(0, max(pos) + 0.06)
            xnames = [SHORT_RULENAMES[r] for r in rules]
            plt.xticks(pos, xnames, rotation=0, fontsize=11)
            upper_labels = [np.median(data[rule]) for rule in rules]
            for i in range(len(pos)):
                plt.text(pos[i], top + 0.06 * (top - bottom),
                         str("{0:.3f}".format(upper_labels[i])),
                         horizontalalignment='center',
                         fontsize=11)
            plot_filename = str("../fig/" + name + ".pdf")
            print("Writing {}".format(plot_filename))
            plt.savefig(plot_filename, bbox_inches='tight')
            # plt.show()
            plt.close()

    matplotlib.rcParams['pdf.fonttype'] = 42
    matplotlib.rcParams['ps.fonttype'] = 42
    matplotlib.rcParams['figure.figsize'] = len(rules)+5, 3

    # average per_quota compliance
    generate_boxplot(aver_quotacompl, 0.5, 1,
                     "aver_quotacompl_" + exp_name)

    # maximum per_quota deviation
    generate_boxplot(max_quotadeviation, 0.7, 5,
                     "max_quota_deviation_" + exp_name)

    # normalized average satisfaction
    norm_aver_satisfaction = {rule: [] for rule in rules}
    for rule in rules:
        norm_aver_satisfaction[rule] = [
            aver_satisfaction[rule][i] / aver_satisfaction["av"][i]
            for i in range(len(aver_satisfaction["av"]))]
    generate_boxplot(norm_aver_satisfaction, 0.7, 1,
                     "normalized_average_satisfaction_" + exp_name)

    # Gini coefficient of influence
    generate_boxplot(aver_influencegini, 0.0, 0.3,
                     "average_Gini_influence_" + exp_name)


def run_exp_for_history(history, aver_quotacompl, max_quotadeviation,
                        aver_satisfaction, aver_influencegini,
                        rules, missing_rule=None):
    voters = get_all_voters(history)
    cands = get_all_candidates(history)

    for rule in rules:
        # print "*" * (len(rule) + 4)
        # print "*",rule.upper(),"*"
        # print "*" * (len(rule) + 4)
        weights = perpetual_rules.init_weights(rule, voters)

        support = dict.fromkeys(voters, 0)
        wins = dict.fromkeys(voters, 0)
        quota_compliance = dict.fromkeys(voters, 0)
        quota_deviation = dict.fromkeys(voters, 0)
        influence = dict.fromkeys(voters, 0)

        for profile in history:
            winner = perpetual.compute_rule(rule, profile,
                                            weights,
                                            missing_rule=missing_rule)
            assert(winner in cands)
            calculate_statistics(profile,
                                 support, wins,
                                 quota_compliance, quota_deviation,
                                 influence, winner)

        quota_compliance = float(sum(quota_compliance.values()))
        quota_compliance = (quota_compliance
                            / len(history)
                            / len(voters))
        aver_quotacompl[rule].append(quota_compliance)

        quota_deviation = float(max(quota_deviation.values()))
        max_quotadeviation[rule].append(quota_deviation)

        satisfaction = float(sum(wins.values()))
        satisfaction = satisfaction / len(history) / len(voters)
        aver_satisfaction[rule].append(satisfaction)

        aver_influencegini[rule].append(
            calculate_gini(listvalues(influence)))


def statistical_significance(name, dataset):
    rules = dataset.keys()
    print("Checking statistical significance of "+name)
    for rule1 in rules:
        for rule2 in rules:
            if rule1 == rule2:
                continue

            _, pvalue = stats.ttest_rel(np.asarray(
                                            dataset[rule1]),
                                        np.asarray(
                                            dataset[rule2]))
            if pvalue > 0.01:
                print(name + " for", rule1, "and", rule2,
                      end=' ')
                print("not significant, p =", pvalue)


def basic_stats(instances):
    av_size = np.average([len(prof.approval_sets[v])
                          for history in instances
                          for prof in history
                          for v in prof.voters])

    print("average approval set size:", av_size)
    num_uncontr = 0
    num_total = 0

    for history in instances:
        for prof in history:
            num_total += 1
            sets = [set(a) for a in prof.approval_sets.values()]
            if len(set.intersection(*sets)) > 0:
                num_uncontr += 1
    print("uncontroversial (unanimous) profiles:", end=' ')
    print(num_uncontr * 100. / num_total, "%")


# generate a list of 2d coordinates subject to
# various distributions
def generate_2d_points(pointids, mode, sigma):

    numpoints = len(pointids)
    points = [0] * numpoints

    # normal distribution, 1/3 of points centered on (-0.5,-0.5),
    #                      2/3 of points on (0.5,0.5)
    #                      all within [-1,1]x[-1,1]
    if mode == "eucl1":
        def within_bounds(point):
            return (point[0] <= 1 and point[0] >= -1 and
                    point[1] <= 1 and point[1] >= -1)
        for i in range(int(numpoints // 3)):
            while True:
                points[i] = (random.gauss(-0.5, sigma),
                             random.gauss(-0.5, sigma))
                if within_bounds(points[i]):
                    break
        for i in range(numpoints // 3, numpoints):
            while True:
                points[i] = (random.gauss(0.5, sigma),
                             random.gauss(0.5, sigma))
                if within_bounds(points[i]):
                    break
    # normal distribution, 1/3 of points centered on (-0.5,-0.5),
    #                      2/3 of points on (0.5,0.5)
    elif mode == "eucl2":
        for i in range(int(numpoints // 3)):
            points[i] = (random.gauss(-0.5, sigma),
                         random.gauss(-0.5, sigma))
        for i in range(int(numpoints // 3), numpoints):
            points[i] = (random.gauss(0.5, sigma),
                         random.gauss(0.5, sigma))
    # normal distribution, 1/5 of points centered on (-0.5,-0.5),
    #                      4/5 of points on (0.5,0.5)
    elif mode == "eucl4":
        for i in range(numpoints // 5):
            points[i] = (random.gauss(-0.5, sigma),
                         random.gauss(-0.5, sigma))
        for i in range(numpoints // 5, numpoints):
            points[i] = (random.gauss(0.5, sigma),
                         random.gauss(0.5, sigma))
    # normal distribution, 3/5 of points centered on (-0.25,0),
    #                      2/5 of points on (0.25,0)
    elif mode == "eucl6":
        for i in range(2 * numpoints // 5):
            points[i] = (random.gauss(-0.25, sigma),
                         random.gauss(0, sigma))
        for i in range(2 * numpoints // 5, numpoints):
            points[i] = (random.gauss(0.25, sigma),
                         random.gauss(0, sigma))
    # normal distribution
    elif mode == "normal":
        for i in range(numpoints):
            points[i] = (random.gauss(0., sigma),
                         random.gauss(0., sigma))
    # normal distribution, each 1/4 of points centered on (+-0.5,+-0.5)
    elif mode == "eucl5":
        for i in range(numpoints // 4):
            points[i] = (random.gauss(-0.5, sigma),
                         random.gauss(-0.5, sigma))
        for i in range(numpoints // 4, 2 * numpoints // 4):
            points[i] = (random.gauss(0.5, sigma),
                         random.gauss(0.5, sigma))
        for i in range(2 * numpoints // 4, 3 * numpoints // 4):
            points[i] = (random.gauss(-0.5, sigma),
                         random.gauss(0.5, sigma))
        for i in range(3 * numpoints // 4, numpoints):
            points[i] = (random.gauss(0.5, sigma),
                         random.gauss(-0.5, sigma))
    # normal distribution, 1/5 of points centered on (-0.5,-0.5),
    #                      1/5 of points centered on (-0.5,0.5),
    #                      1/5 of points centered on (0.5,-0.5),
    #                      2/5 of points on (0.5,0.5)
    elif mode == "eucl3":
        for i in range(numpoints // 5):
            points[i] = (random.gauss(-0.5, sigma),
                         random.gauss(-0.5, sigma))
        for i in range(numpoints // 5, 2 * numpoints // 5):
            points[i] = (random.gauss(-0.5, sigma),
                         random.gauss(0.5, sigma))
        for i in range(2 * numpoints // 5, 3 * numpoints // 5):
            points[i] = (random.gauss(0.5, sigma),
                         random.gauss(-0.5, sigma))
        for i in range(3 * numpoints // 5, numpoints):
            points[i] = (random.gauss(0.5, sigma),
                         random.gauss(0.5, sigma))
    elif mode == "eucl2plus":
        for i in range(numpoints // 6):
            points[i] = (random.gauss(-0.5, sigma),
                         random.gauss(-0.5, sigma))
        for i in range(numpoints // 6, numpoints):
            points[i] = (random.gauss(0.5, sigma),
                         random.gauss(0.5, sigma))
    elif mode == "uniform_square":
        for i in range(numpoints):
            points[i] = (random.uniform(-1, 1),
                         random.uniform(-1, 1))
    else:
        print("mode", mode, "not known")
        quit()

    pointsdict = {}
    random.shuffle(points)
    for i in range(numpoints):
        pointsdict[pointids[i]] = points[i]

    return pointsdict


# generate instances for experiments according to specifications
def generate_instances(exp_specs):
    instances = {}
    for spec in exp_specs:
        if spec == "full":
            continue

        # load instances from a pickle file if it exists
        # or generate instances and save to pickle file
        name = str(spec).replace("]", "").replace("[", "")
        name = name.replace(" ", "").replace("'", "")
        picklefile = "../pickle/experiments-" + name + ".pickle"
        if not exists(picklefile):
            print("generating instances for spec", spec)
            (num_simulations, num_voters, num_cands, num_rounds,
             sigma, voterpointmode, candpointmode,
             approval_threshold) = spec

            instances[str(spec)] = []
            for _ in range(num_simulations):

                voters = list(range(num_voters))
                cands = list(range(num_cands))
                voter_points = generate_2d_points(voters, voterpointmode,
                                                  sigma)

                # plt.scatter([x for x,y in voter_points.values()],
                #             [y for x,y in voter_points.values()])
                # plt.show()

                history = []
                for _ in range(num_rounds):
                    cand_points = generate_2d_points(cands, candpointmode,
                                                     sigma)
                    prof = profiles.approvalprofile_from_2d_euclidean(
                        voters,
                        cands,
                        voter_points,
                        cand_points,
                        approval_threshold)
                    history.append(prof)
                instances[str(spec)].append(history)

            print("writing instances to", picklefile)
            with open(picklefile, 'wb') as f:
                pickle.dump(instances[str(spec)], f, protocol=2)
        else:
            print("loading instances from", picklefile)
            with open(picklefile, 'rb') as f:
                instances[str(spec)] = pickle.load(f)

    return instances

# lots of simulations, three statistics
# 1) AV score
# 2) perpetual quota: sum up over all rounds,
#             how many voters had perp per_quota satisfied in this round
# 3) gini of influence: again, normalize by optimum
# 4) not implemented: max dry spell

# variables in exp_specs:
# num_simulations, num_voters, num_cands, num_rounds
# sigma, voterpointmode, candpointmode, approval_threshold

# exp_specs = [
#     [1000, 20, 5, 20, 0.2, "eucl5", "uniform_square", 1.5],
#     [1000, 20, 5, 20, 0.1, "eucl5", "uniform_square", 1.5],
#     [1000, 20, 5, 20, 0.2, "eucl6", "uniform_square", 1.5],
#     [1000, 20, 5, 20, 0.1, "eucl6", "uniform_square", 1.5],
#     [1000, 20, 5, 20, 0.2, "normal", "normal", 1.5],
#     [1000, 20, 5, 20, 0.1, "normal", "normal", 1.5],
#     [1000, 20, 5, 20, 0.2, "eucl2", "uniform_square", 1.5],
#     [1000, 20, 5, 20, 0.1, "eucl2", "uniform_square", 1.5],
#     [1000, 20, 5, 20, 0.2, "eucl1", "uniform_square", 1.5],
#     [1000, 20, 5, 20, 0.1, "eucl1", "uniform_square", 1.5],
#     [1000, 20, 5, 20, None, "uniform_square", "uniform_square", 1.5],
#     [1000, 50, 5, 20, 0.2, "eucl5", "uniform_square", 1.5],
#     [1000, 50, 5, 20, 0.1, "eucl5", "uniform_square", 1.5],
#     [1000, 50, 5, 20, 0.2, "eucl6", "uniform_square", 1.5],
#     [1000, 50, 5, 20, 0.1, "eucl6", "uniform_square", 1.5],
#     [1000, 50, 5, 20, 0.2, "normal", "normal", 1.5],
#     [1000, 50, 5, 20, 0.1, "normal", "normal", 1.5],
#     [1000, 50, 5, 20, 0.2, "eucl2", "uniform_square", 1.5],
#     [1000, 50, 5, 20, 0.1, "eucl2", "uniform_square", 1.5],
#     [1000, 50, 5, 20, 0.2, "eucl1", "uniform_square", 1.5],
#     [1000, 50, 5, 20, 0.1, "eucl1", "uniform_square", 1.5],
#     [1000, 50, 5, 20, None, "uniform_square", "uniform_square", 1.5],
#     "full"]


try:
    makedirs("../pickle")
except OSError:
    if not isdir("../pickle"):
        raise
try:
    makedirs("../fig")
except OSError:
    if not isdir("../fig"):
        raise
