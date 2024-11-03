import psycopg2
from psycopg2 import sql
from dbconfig import HOST, PORT, DATABASE, USER, SECRET 

try:
  connection = psycopg2.connect(
        host = HOST,
        port = PORT,
        database = DATABASE,
        user = USER,
        password = SECRET
  )

  cursor = connection.cursor()
  print("Успешно подключено к PostgreSQL")

  def fetch_data():
    cursor.execute('''SELECT * FROM users''')
    data = cursor.fetchall()
    return data

  details = fetch_data()
  for row in details:
      print(row)

except Exception as err:
    print("Что-то пошло не так...", err)

finally:
    if 'connection' in locals() and connection:
        cursor.close()
        connection.close()
        print("Соединение с PostgreSQL закрыто")