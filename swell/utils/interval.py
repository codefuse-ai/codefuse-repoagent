from intervaltree import IntervalTree


def merge_overlapping_intervals(intervals, merge_continuous=False):
    iv_tree = IntervalTree.from_tuples(intervals)
    iv_tree.merge_overlaps()
    intervals = [(iv.begin, iv.end) for iv in iv_tree]
    intervals.sort()
    # [30, 50) and [50, 60) won't be merged as they do not overlap
    if not merge_continuous:
        return intervals
    # Merge [30, 50) and [50, 60) into [30, 60)
    refined = []
    for iv in intervals:
        if len(refined) > 0 and refined[-1][1] == iv[0]:
            refined[-1] = (refined[-1][0], iv[1])
        else:
            refined.append(iv)
    return refined
