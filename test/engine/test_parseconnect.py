from sqlalchemy.test.testing import assert_raises, assert_raises_message
import ConfigParser
import StringIO
import sqlalchemy.engine.url as url
from sqlalchemy import create_engine, engine_from_config
import sqlalchemy as tsa
from sqlalchemy.test import TestBase


class ParseConnectTest(TestBase):
    def test_rfc1738(self):
        for text in (
            'dbtype://username:password@hostspec:110//usr/db_file.db',
            'dbtype://username:password@hostspec/database',
            'dbtype://username:password@hostspec',
            'dbtype://username:password@/database',
            'dbtype://username@hostspec',
            'dbtype://username:password@127.0.0.1:1521',
            'dbtype://hostspec/database',
            'dbtype://hostspec',
            'dbtype://hostspec/?arg1=val1&arg2=val2',
            'dbtype:///database',
            'dbtype:///:memory:',
            'dbtype:///foo/bar/im/a/file',
            'dbtype:///E:/work/src/LEM/db/hello.db',
            'dbtype:///E:/work/src/LEM/db/hello.db?foo=bar&hoho=lala',
            'dbtype://',
            'dbtype://username:password@/db',
            'dbtype:////usr/local/mailman/lists/_xtest@example.com/members.db',
            'dbtype://username:apples%2Foranges@hostspec/mydatabase',
        ):
            u = url.make_url(text)
            assert u.drivername == 'dbtype'
            assert u.username == 'username' or u.username is None
            assert u.password == 'password' or u.password == 'apples/oranges' or u.password is None
            assert u.host == 'hostspec' or u.host == '127.0.0.1' or (not u.host)
            assert str(u) == text

class CreateEngineTest(TestBase):
    """test that create_engine arguments of different types get propagated properly"""
    def test_connect_query(self):
        dbapi = MockDBAPI(foober='12', lala='18', fooz='somevalue')

        e = create_engine(
                'postgresql://scott:tiger@somehost/test?foober=12&lala=18&fooz=somevalue', 
                module=dbapi,
                _initialize=False
                )
        c = e.connect()

    def test_kwargs(self):
        dbapi = MockDBAPI(foober=12, lala=18, hoho={'this':'dict'}, fooz='somevalue')

        e = create_engine(
                'postgresql://scott:tiger@somehost/test?fooz=somevalue', 
                connect_args={'foober':12, 'lala':18, 'hoho':{'this':'dict'}}, 
                module=dbapi,
                _initialize=False
                )
        c = e.connect()

    def test_coerce_config(self):
        raw = r"""
[prefixed]
sqlalchemy.url=postgresql://scott:tiger@somehost/test?fooz=somevalue
sqlalchemy.convert_unicode=0
sqlalchemy.echo=false
sqlalchemy.echo_pool=1
sqlalchemy.max_overflow=2
sqlalchemy.pool_recycle=50
sqlalchemy.pool_size=2
sqlalchemy.pool_threadlocal=1
sqlalchemy.pool_timeout=10
[plain]
url=postgresql://scott:tiger@somehost/test?fooz=somevalue
convert_unicode=0
echo=0
echo_pool=1
max_overflow=2
pool_recycle=50
pool_size=2
pool_threadlocal=1
pool_timeout=10
"""
        ini = ConfigParser.ConfigParser()
        ini.readfp(StringIO.StringIO(raw))

        expected = {
            'url': 'postgresql://scott:tiger@somehost/test?fooz=somevalue',
            'convert_unicode': 0,
            'echo': False,
            'echo_pool': True,
            'max_overflow': 2,
            'pool_recycle': 50,
            'pool_size': 2,
            'pool_threadlocal': True,
            'pool_timeout': 10,
            }

        prefixed = dict(ini.items('prefixed'))
        self.assert_(tsa.engine._coerce_config(prefixed, 'sqlalchemy.') == expected)

        plain = dict(ini.items('plain'))
        self.assert_(tsa.engine._coerce_config(plain, '') == expected)

    def test_engine_from_config(self):
        dbapi = MockDBAPI()

        config = {
            'sqlalchemy.url':'postgresql://scott:tiger@somehost/test?fooz=somevalue',
            'sqlalchemy.pool_recycle':'50',
            'sqlalchemy.echo':'true'
        }

        e = engine_from_config(config, module=dbapi)
        assert e.pool._recycle == 50
        assert e.url == url.make_url('postgresql://scott:tiger@somehost/test?fooz=somevalue')
        assert e.echo is True

    def test_custom(self):
        dbapi = MockDBAPI(foober=12, lala=18, hoho={'this':'dict'}, fooz='somevalue')

        def connect():
            return dbapi.connect(foober=12, lala=18, fooz='somevalue', hoho={'this':'dict'})

        # start the postgresql dialect, but put our mock DBAPI as the module instead of psycopg
        e = create_engine('postgresql://', creator=connect, module=dbapi, _initialize=False)
        c = e.connect()

    def test_recycle(self):
        dbapi = MockDBAPI(foober=12, lala=18, hoho={'this':'dict'}, fooz='somevalue')
        e = create_engine('postgresql://', pool_recycle=472, module=dbapi, _initialize=False)
        assert e.pool._recycle == 472

    def test_badargs(self):
        assert_raises(ImportError, create_engine, "foobar://", module=MockDBAPI())

        # bad arg
        assert_raises(TypeError, create_engine, 'postgresql://', use_ansi=True, module=MockDBAPI())

        # bad arg
        assert_raises(TypeError, create_engine, 'oracle://', lala=5, use_ansi=True, module=MockDBAPI())

        assert_raises(TypeError, create_engine, 'postgresql://', lala=5, module=MockDBAPI())

        assert_raises(TypeError, create_engine,'sqlite://', lala=5)

        assert_raises(TypeError, create_engine, 'mysql+mysqldb://', use_unicode=True, module=MockDBAPI())

        # sqlite uses SingletonThreadPool which doesnt have max_overflow
        assert_raises(TypeError, create_engine, 'sqlite://', max_overflow=5)

        # raises DBAPIerror due to use_unicode not a sqlite arg
        e = create_engine('sqlite://', connect_args={'use_unicode':True}, convert_unicode=True)
        assert_raises(tsa.exc.DBAPIError, e.connect)

    def test_urlattr(self):
        """test the url attribute on ``Engine``."""

        e = create_engine('mysql://scott:tiger@localhost/test', module=MockDBAPI(), _initialize=False)
        u = url.make_url('mysql://scott:tiger@localhost/test')
        e2 = create_engine(u, module=MockDBAPI(), _initialize=False)
        assert e.url.drivername == e2.url.drivername == 'mysql'
        assert e.url.username == e2.url.username == 'scott'
        assert e2.url is u

    def test_poolargs(self):
        """test that connection pool args make it thru"""
        e = create_engine('postgresql://', creator=None, pool_recycle=50, echo_pool=None, module=MockDBAPI(), _initialize=False)
        assert e.pool._recycle == 50

        # these args work for QueuePool
        e = create_engine('postgresql://', max_overflow=8, pool_timeout=60, poolclass=tsa.pool.QueuePool, module=MockDBAPI())

        # but not SingletonThreadPool
        assert_raises(TypeError, create_engine, 'sqlite://', max_overflow=8, pool_timeout=60, poolclass=tsa.pool.SingletonThreadPool)

class MockDBAPI(object):
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.paramstyle = 'named'
    def connect(self, *args, **kwargs):
        for k in self.kwargs:
            assert k in kwargs, "key %s not present in dictionary" % k
            assert kwargs[k]==self.kwargs[k], "value %s does not match %s" % (kwargs[k], self.kwargs[k])
        return MockConnection()
class MockConnection(object):
    def get_server_info(self):
        return "5.0"
    def close(self):
        pass
    def cursor(self):
        return MockCursor()
class MockCursor(object):
    def close(self):
        pass
mock_dbapi = MockDBAPI()

