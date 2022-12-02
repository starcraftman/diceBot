"""
Followed simple tutorial for tutorial on motor.

See: https://motor.readthedocs.io/en/stable/tutorial-asyncio.html
"""
import asyncio

#  from bson import SON
import motor.motor_asyncio


async def async_main():
    """
    Basic demo of operations.
    """
    client = motor.motor_asyncio.AsyncIOMotorClient('mongodb://localhost:31000')
    db = client.dice
    await db.basic_test.drop()

    #  result = await db.basic_test.replace_one({'i': 555}, {'i': 555, 'key': 'value'}, True)

    #  result = await db.basic_test.insert_one({'i': 555})
    #  result = await db.basic_test.delete_one({'i': 555})
    #  print(result.deleted_count)

    #  for x in await db.list_collections():
        #  print(x)

    #  result = await db.basic_test.insert_many(
        #  [{'i': i} for i in range(2000)]
    #  )
    #  print('inserted %d docs' % (len(result.inserted_ids),))

    #  print(await db.basic_test.find_one({'i': {'$lt': 1}}))

    #  print(await db.basic_test.find_one({'i': {'$gt': 1000000}}))

    #  async for found in db.basic_test.find({'i': {'$lt': 15}}):
        #  print(found)

    #  cursor = db.basic_test.find({'i': {'$lt': 15}})
    #  cursor.sort('i', -1).skip(3).limit(5)
    #  async for found in cursor:
        #  print(found)

    #  cnt = await db.basic_test.count_documents({'i': {'$gt': 1000}})
    #  print(f'{cnt} documents where i > 1000')

    #  old_doc = await db.basic_test.find_one({'i': 50})
    #  print(f"Found {old_doc}")
    #  result = await db.basic_test.replace_one({'i': 50}, {'i': 50, 'key': 'value'})
    #  print(f'replaced {result.modified_count}')
    #  new_doc = await db.basic_test.find_one({'i': 50})
    #  print(f"Found {new_doc}")

    #  old_doc = await db.basic_test.find_one({'i': 50})
    #  print(f"Found {old_doc}")
    #  result = await db.basic_test.update_one({'i': 50}, {'$set': {'key': 'another value here'}})
    #  print(f'replaced {result.modified_count}')
    #  new_doc = await db.basic_test.find_one({'i': 50})
    #  print(f"Found {new_doc}")

    #  cnt = await db.basic_test.count_documents({'i': {'$gt': 1000}})
    #  print(f'{cnt} documents where i > 1000')
    #  await db.basic_test.delete_many({'i': {'$gt': 1000}})
    #  cnt = await db.basic_test.count_documents({'i': {'$gt': 1000}})
    #  print(f'{cnt} documents where i > 1000')

    #  response = await db.command(
        #  SON([
            #  ("distinct", "basic_test"),
            #  ("key", "i")
        #  ])
    #  )
    #  print(str(response))

    #  print(dir(db.basic_test))


def main():
    asyncio.new_event_loop().run_until_complete(async_main())


if __name__ == "__main__":
    main()
