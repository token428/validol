from itertools import groupby

from model.store.miners.monetary import Monetary
from model.store.resource import Resource


class MonetaryDelta(Resource):
    SCHEMA = [("MBDelta", "REAL")]

    def __init__(self, dbh):
        Resource.__init__(self, dbh, "MonetaryDelta", MonetaryDelta.SCHEMA)

        self.source = Monetary(dbh)

    def deltas(self, mbase):
        grouped_mbase = [(mbase[0], 1)] + [(k, len(list(g))) for k, g in groupby(mbase)]
        deltas = []
        for i in range(1, len(grouped_mbase)):
            k, n = grouped_mbase[i]
            delta = k - grouped_mbase[i - 1][0]

            for j in range(n):
                deltas.append(delta / n)

        return deltas

    def fill(self, first, last):
        return self.initial_fill()

    def initial_fill(self):
        df = self.source.read_dates().rename(str, {"MBase": "MBDelta"})
        df.MBDelta = self.deltas(df.MBDelta)
        return df

    # not optimal, but who cares