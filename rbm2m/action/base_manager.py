# -*- coding: utf-8 -*-


class BaseManager(object):

    """
        Base class for database managers
    """
    __model__ = None

    def __init__(self, session):
        self.session = session

    def get(self, item_id):
        """
            Get object by id
        """
        return self.session.query(self.__model__).get(item_id)

    def from_dict(self, d):
        """
            Create new instance with properties set from _values
        """
        obj = self.__model__(**d)
        self.session.add(obj)
        self.session.flush()
        return obj

    def merge_from_dict(self, d):
        """
            Create or merge an instance with properties set from _values
        """
        obj = self.session.query(self.__model__).get(d['id'])
        if not obj:
            obj = self.__model__(**d)
            self.session.add(obj)
        else:
            for k in d:
                setattr(obj,k,d[k])
        self.session.merge(obj)
        self.session.flush()
        return obj

    def all(self):
        """
            Return all entities
        """
        return self.session.query(self.__model__).all()

    def find(self, **kwargs):
        """
            Returns a list of instances of the service's model filtered by the
            specified key word arguments.
        """
        return self.session.query(self.__model__).filter_by(**kwargs)

    def get_or_insert(self, **kwargs):
        """
            Find and return first entry or create a new one
        """
        entry = self.find(**kwargs).first()
        if not entry:
            entry = self.from_dict(kwargs)

        return entry

    def delete(self, entry):
        """
            Delete entry from db
        """
        self.session.delete(entry)

    def delete_by_id(self, pk):
        """
            Delete entry by id
        """
        entry = self.get(pk)
        self.delete(entry)

    def delete_all(self):
        """
            Delete all records from table
        """
        return self.session.query(self.__model__).delete()
