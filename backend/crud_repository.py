from psycopg2 import sql


class CrudRepository:
    """Operações de escrita comuns para uma tabela e colunas previamente permitidas."""

    def __init__(
        self,
        connection_factory,
        table,
        id_column,
        writable_columns,
        schema='public',
        generate_integer_id=False,
    ):
        self.connection_factory = connection_factory
        self.schema = schema
        self.table = table
        self.id_column = id_column
        self.writable_columns = frozenset(writable_columns)
        self.generate_integer_id = generate_integer_id

    def _validated_values(self, values):
        if not values:
            raise ValueError('Nenhum dado informado.')
        invalid = set(values) - self.writable_columns
        if invalid:
            raise ValueError('Foram informados campos não permitidos.')
        return values

    def create(self, values):
        values = self._validated_values(values)
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                values = dict(values)
                if self.generate_integer_id:
                    # Serializa a geração para tabelas legadas sem sequence/default.
                    cursor.execute(
                        'SELECT pg_advisory_xact_lock(hashtext(%s))',
                        (f'{self.schema}.{self.table}',),
                    )
                    cursor.execute(sql.SQL('SELECT COALESCE(MAX({}), 0) + 1 FROM {}.{}').format(
                        sql.Identifier(self.id_column),
                        sql.Identifier(self.schema),
                        sql.Identifier(self.table),
                    ))
                    values[self.id_column] = cursor.fetchone()[0]

                columns = list(values)
                statement = sql.SQL(
                    'INSERT INTO {}.{} ({}) VALUES ({}) RETURNING {}'
                ).format(
                    sql.Identifier(self.schema),
                    sql.Identifier(self.table),
                    sql.SQL(', ').join(map(sql.Identifier, columns)),
                    sql.SQL(', ').join(sql.Placeholder() for _ in columns),
                    sql.Identifier(self.id_column),
                )
                cursor.execute(statement, [values[column] for column in columns])
                return cursor.fetchone()[0]

    def update(self, record_id, values):
        values = self._validated_values(values)
        columns = list(values)
        assignments = sql.SQL(', ').join(
            sql.SQL('{} = {}').format(sql.Identifier(column), sql.Placeholder())
            for column in columns
        )
        statement = sql.SQL('UPDATE {}.{} SET {} WHERE {} = {} RETURNING {}').format(
            sql.Identifier(self.schema),
            sql.Identifier(self.table),
            assignments,
            sql.Identifier(self.id_column),
            sql.Placeholder(),
            sql.Identifier(self.id_column),
        )
        parameters = [values[column] for column in columns] + [record_id]
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                return cursor.fetchone() is not None

    def delete(self, record_id):
        statement = sql.SQL('DELETE FROM {}.{} WHERE {} = {} RETURNING {}').format(
            sql.Identifier(self.schema),
            sql.Identifier(self.table),
            sql.Identifier(self.id_column),
            sql.Placeholder(),
            sql.Identifier(self.id_column),
        )
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, (record_id,))
                return cursor.fetchone() is not None
