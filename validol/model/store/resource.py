import datetime as dt
import pandas as pd
import numpy as np
from functools import wraps, partial

from validol.model.utils import date_to_timestamp, to_timestamp


class Table:
    def __init__(self, dbh, table, schema, modifier="", pre_dump=None, post_load=None):
        self.schema = [(name, data_type) for name, data_type in schema]
        self.table = table
        self.dbh = dbh
        self.pre_dump = pre_dump or (lambda x: x)
        self.post_load = post_load or (lambda x: x)

        self.__create_table(modifier)

    def __create_table(self, modifier):
        columns = [" ".join(['"{}"'.format(name), data_type]) for name, data_type in self.schema]

        if modifier:
            modifier = ", " + modifier

        self.dbh.cursor().execute(
            'CREATE TABLE IF NOT EXISTS "{table}" ({columns}{modifier})'.format(
                table=self.table,
                columns=",".join(columns),
                modifier=modifier))

    def read_all(self, query):
        return self.dbh.cursor().execute(query).fetch_all()

    def write(self, values):
        self.dbh.cursor().executemany('''
            INSERT INTO
                {table}
            VALUES
                ({values_num})
        '''.format(table=self.table, values_num=",".join('?' * len(self.schema))), values)

    def write_df(self, df):
        self.pre_dump(df).to_sql(self.table, self.dbh, if_exists='append', index=False)

    def read_df(self, query=None, **kwargs):
        if query is None:
            query = 'SELECT * FROM "{table}"'
        return self.post_load(pd.read_sql(query.format(table=self.table), self.dbh, **kwargs))

    def drop(self):
        self.dbh.cursor().execute('''
            DROP TABLE IF EXISTS
                "{table}"
        '''.format(table=self.table))


class Updater:
    @staticmethod
    def reduce_ranges(ranges):
        return [f(l) if l else None for f, l in
                zip((min, max), map(lambda x: list(filter(None.__ne__, x)), zip(*ranges)))]

    def __init__(self, model_launcher):
        self.model_launcher = model_launcher

    def update_source(self, source):
        result = self.update_source_impl(source)

        results = [] if result is None else [(source, result)]

        for dep, sources in self.dependencies(source):
            updater = dep(self.model_launcher)

            if sources is None:
                results.extend(updater.update_entire())
            else:
                for source in sources:
                    results.extend(updater.update_source(source))

        return results

    def update_source_impl(self, source):
        raise NotImplementedError

    def get_sources(self):
        raise NotImplementedError

    def update_entire(self):
        results = []

        for source in self.get_sources():
            results.extend(self.update_source(source['name']))

        return results

    def dependencies(self, source):
        return []

    def verbose(self, source):
        return True


class FlavorUpdater(Updater):
    def __init__(self, model_launcher, flavors):
        Updater.__init__(self, model_launcher)

        self.flavors_map = {flavor['name']: flavor for flavor in flavors}

    def update_source_impl(self, source):
        return self.update_flavor(self.flavors_map[source])

    def update_flavor(self, flavor):
        raise NotImplementedError

    def get_sources(self):
        return list(self.flavors_map.values())

    def flavor_dependencies(self, flavor):
        return []

    def dependencies(self, source):
        return self.flavor_dependencies(self.flavors_map[source])


class Updatable:
    @staticmethod
    def range_from_timestamp(range):
        if range != (None, None):
            return map(dt.date.fromtimestamp, range)
        else:
            return range

    def update(self):
        first, last = self.range()

        if first is not None:
            if last != dt.date.today():
                info = self.fill(last + dt.timedelta(days=1), dt.date.today())
            else:
                return None, None
        else:
            info = self.initial_fill()

        self.write_update(info)

        return self.get_range(info)

    def initial_fill(self):
        raise NotImplementedError

    def fill(self, first, last):
        raise NotImplementedError

    def range(self):
        raise NotImplementedError

    def write_update(self, data):
        raise NotImplementedError

    def get_range(self, info):
        raise NotImplementedError


class Resource(Table, Updatable):
    def __init__(self, dbh, table, schema, modifier=None, pre_dump=None, post_load=None):
        Table.__init__(self, dbh, table, [("Date", "INTEGER")] + schema,
                       modifier or "PRIMARY KEY (Date) ON CONFLICT IGNORE",
                       pre_dump, post_load)
        Updatable.__init__(self)

    def range(self):
        c = self.dbh.cursor()
        c.execute('''
        SELECT
            MIN(Date),
            MAX(Date)
        FROM
            "{table}"'''.format(table=self.table))

        return Updatable.range_from_timestamp(c.fetchone())

    def empty(self):
        return pd.DataFrame(columns=[name for name, _ in self.schema],
                            dtype=np.float64)

    def read_dates_dt(self, *args):
        return self.read_dates_ts(*map(to_timestamp, args))

    def read_dates_ts(self, begin=None, end=None):
        query = '''
            SELECT 
                * 
            FROM 
                "{table}"'''.format(table=self.table)

        cp = list(zip(*[(clause, int(param))
                        for clause, param in (('Date >= ?', begin), ('Date <= ?', end))
                        if param is not None]))

        if cp:
            clauses, params = cp

            query += 'WHERE {}'.format(' AND '.join(clauses))
        else:
            params = None

        return self.read_df(query, params=params)

    def read_df(self, query=None, index_on=True, **kwargs):
        if index_on:
            kwargs['index_col'] = 'Date'

        df = super().read_df(query, **kwargs)

        if index_on:
            df.sort_index(inplace=True)

        return df

    def write_df(self, df):
        if not df.empty and df.Date.dtype != np.int64:
            df = date_to_timestamp(df)

        super().write_df(df)

    def write_update(self, data):
        self.write_df(data)

    def get_range(self, info):
        if info.empty:
            return None, None
        else:
            return [info.iloc[i].Date for i in (0, -1)]

    @staticmethod
    def get_atoms(schema):
        return [atom[0] for atom in schema]

    @staticmethod
    def get_flavor_atoms(flavor):
        if flavor.get('atoms_donor', True):
            return Resource.get_atoms(flavor.get("schema", []))
        else:
            return []


class ResourceUpdater(Resource, Updater):
    def __init__(self, model_launcher, dbh, table, schema,
                 modifier=None, pre_dump=None, post_load=None):
        Resource.__init__(self, dbh, table, schema, modifier, pre_dump, post_load)
        Updater.__init__(self, model_launcher)

    def update_source_impl(self, source):
        return self.update()

    def get_sources(self):
        return [{'name': self.table}]


class Platforms(Table):
    def __init__(self, model_launcher, flavor):
        Table.__init__(
            self,
            model_launcher.main_dbh,
            "Platforms_{flavor}".format(flavor=flavor), [
                ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
                ("PlatformCode", "TEXT"),
                ("PlatformName", "TEXT")],
            "UNIQUE (PlatformCode) ON CONFLICT IGNORE")

    def get_platforms(self):
        return self.read_df()

    def get_platform_id(self, platform_code):
        return self.dbh.cursor().execute('''
            SELECT 
                id 
            FROM 
                "{table}" 
            WHERE 
                PlatformCode = ?'''.format(table=self.table), (platform_code,)).fetchone()[0]

class Actives(Table):
    def __init__(self, dbh, flavor, schema_add=None):
        schema = [
            ("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
            ("PlatformCode", "TEXT"),
            ("ActiveName", "TEXT")]

        if schema_add is not None:
            schema.extend(schema_add)

        Table.__init__(self, dbh,
                       "Actives_{flavor}".format(flavor=flavor), schema,
                       "UNIQUE (PlatformCode, ActiveName) ON CONFLICT IGNORE")

    def get_actives(self, platform):
        return self.read_df('''
            SELECT
                *
            FROM
                "{table}"
            WHERE
                PlatformCode = ?''', params=(platform,))

    def get_fields(self, platform_code, active_name, fields):
        return self.dbh.cursor().execute('''
            SELECT 
                {fields} 
            FROM 
                "{table}" 
            WHERE 
                PlatformCode = ? AND 
                ActiveName = ?'''.format(table=self.table, fields=', '.join(fields)),
                                         (platform_code, active_name)).fetchone()

    def remove_active(self, ai):
        self.dbh.cursor().execute('''
            DELETE 
            FROM 
                "{table}" 
            WHERE
                PlatformCode = ? AND 
                ActiveName = ?'''.format(table=self.table), (ai.platform, ai.active))

        self.dbh.commit()


class ActiveResource(Resource):
    def __init__(self, schema, model_launcher, platform_code, active_name, flavor,
                 platforms_cls=Platforms, actives_cls=Actives, modifier=None,
                 pre_dump=None, post_load=None, actives_flavor=None):
        active_id = actives_cls(model_launcher, actives_flavor or flavor).get_fields(platform_code, active_name, ('id',))[0]
        platform_id = platforms_cls(model_launcher, actives_flavor or flavor).get_platform_id(platform_code)

        Resource.__init__(self, model_launcher.main_dbh,
                          "Active_platform_{platform_id}_active_{active_id}_{flavor}".format(
                              platform_id=platform_id,
                              active_id=active_id,
                              flavor=flavor),
                          schema, modifier, pre_dump, post_load)


def check_empty(f):
    @wraps(f)
    def wrapped(df):
        if df.empty:
            return df
        else:
            return f(df)

    return wrapped