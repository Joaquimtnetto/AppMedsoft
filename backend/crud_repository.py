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
        tenant_column=None,
        tenant_value_factory=None,
    ):
        self.connection_factory = connection_factory
        self.schema = schema
        self.table = table
        self.id_column = id_column
        self.writable_columns = frozenset(writable_columns)
        self.generate_integer_id = generate_integer_id
        self.tenant_column = tenant_column
        self.tenant_value_factory = tenant_value_factory

    def _tenant_value(self):
        if not self.tenant_column:
            return None
        if not self.tenant_value_factory:
            raise ValueError('Empresa não configurada para esta operação.')
        return self.tenant_value_factory()

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
                if self.tenant_column:
                    # O tenant sempre vem da sessão, ignorando qualquer valor do cliente.
                    values[self.tenant_column] = self._tenant_value()
                if self.generate_integer_id and self.id_column != self.tenant_column:
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
        where = sql.SQL('{} = {}').format(
            sql.Identifier(self.id_column), sql.Placeholder()
        )
        parameters = [values[column] for column in columns] + [record_id]
        if self.tenant_column:
            where += sql.SQL(' AND {} = {}').format(
                sql.Identifier(self.tenant_column), sql.Placeholder()
            )
            parameters.append(self._tenant_value())
        statement = sql.SQL('UPDATE {}.{} SET {} WHERE {} RETURNING {}').format(
            sql.Identifier(self.schema),
            sql.Identifier(self.table),
            assignments,
            where,
            sql.Identifier(self.id_column),
        )
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                return cursor.fetchone() is not None

    def delete(self, record_id):
        where = sql.SQL('{} = {}').format(
            sql.Identifier(self.id_column), sql.Placeholder()
        )
        parameters = [record_id]
        if self.tenant_column:
            where += sql.SQL(' AND {} = {}').format(
                sql.Identifier(self.tenant_column), sql.Placeholder()
            )
            parameters.append(self._tenant_value())
        statement = sql.SQL('DELETE FROM {}.{} WHERE {} RETURNING {}').format(
            sql.Identifier(self.schema),
            sql.Identifier(self.table),
            where,
            sql.Identifier(self.id_column),
        )
        with self.connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                return cursor.fetchone() is not None
