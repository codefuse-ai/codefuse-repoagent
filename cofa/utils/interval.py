from intervaltree import IntervalTree


def merge_overlapping_intervals(intervals):
    iv_tree = IntervalTree.from_tuples(intervals)
    iv_tree.merge_overlaps()
    intervals = [(iv.begin, iv.end) for iv in iv_tree]
    intervals.sort()
    return intervals
