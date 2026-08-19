import fdb

config = {
    'host': '24.152.36.178',
    'database': 'C:/JTN/Medsoft/2-Migracao/BD/medico3.fdb',
    'user': 'sysdba',
    'password': 'masterkey',
    'port': 3050
}

termo_busca = '%joa%'
nome_medico = 'CARLOS RODRIGUES BRODSKY'

try:
    con = fdb.connect(**config)
    cur = con.cursor()
    query = '''
        SELECT nomecli, codcli, datanasc_, nomeplano1, nomed
        FROM Pacient
        WHERE UPPER(nomecli) LIKE UPPER(?)
          AND UPPER(nomed) = UPPER(?)
        ORDER BY nomecli
    '''
    cur.execute(query, (termo_busca, nome_medico))
    rows = cur.fetchall()
    con.close()
except Exception as e:
