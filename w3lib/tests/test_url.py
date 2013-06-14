import os
import unittest
from w3lib.url import safe_url_string, safe_download_url, \
    url_query_parameter, add_or_replace_parameter, url_query_cleaner, \
    file_uri_to_path, path_to_file_uri, any_to_uri

class UrlTests(unittest.TestCase):

    def test_safe_url_string(self):
        # Motoko Kusanagi (Cyborg from Ghost in the Shell)
        motoko = u'\u8349\u8599 \u7d20\u5b50'
        self.assertEqual(safe_url_string(motoko),  # note the %20 for space
                        '%E8%8D%89%E8%96%99%20%E7%B4%A0%E5%AD%90')
        self.assertEqual(safe_url_string(motoko),
                         safe_url_string(safe_url_string(motoko)))
        self.assertEqual(safe_url_string(u'\xa9'), # copyright symbol
                         '%C2%A9')
        self.assertEqual(safe_url_string(u'\xa9', 'iso-8859-1'),
                         '%A9')
        self.assertEqual(safe_url_string("http://www.example.org/"),
                        'http://www.example.org/')

        alessi = u'/ecommerce/oggetto/Te \xf2/tea-strainer/1273'

        self.assertEqual(safe_url_string(alessi),
                         '/ecommerce/oggetto/Te%20%C3%B2/tea-strainer/1273')

        self.assertEqual(safe_url_string("http://www.example.com/test?p(29)url(http://www.another.net/page)"),
                                         "http://www.example.com/test?p(29)url(http://www.another.net/page)")
        self.assertEqual(safe_url_string("http://www.example.com/Brochures_&_Paint_Cards&PageSize=200"),
                                         "http://www.example.com/Brochures_&_Paint_Cards&PageSize=200")

        safeurl = safe_url_string(u"http://www.example.com/\xa3", encoding='latin-1')
        self.assert_(isinstance(safeurl, str))
        self.assertEqual(safeurl, "http://www.example.com/%A3")

        safeurl = safe_url_string(u"http://www.example.com/\xa3", encoding='utf-8')
        self.assert_(isinstance(safeurl, str))
        self.assertEqual(safeurl, "http://www.example.com/%C2%A3")

    def test_safe_download_url(self):
        self.assertEqual(safe_download_url('http://www.example.org/../'),
                         'http://www.example.org/')
        self.assertEqual(safe_download_url('http://www.example.org/../../images/../image'),
                         'http://www.example.org/image')
        self.assertEqual(safe_download_url('http://www.example.org/dir/'),
                         'http://www.example.org/dir/')

    def test_url_query_parameter(self):
        self.assertEqual(url_query_parameter("product.html?id=200&foo=bar", "id"),
                         '200')
        self.assertEqual(url_query_parameter("product.html?id=200&foo=bar", "notthere", "mydefault"),
                         'mydefault')
        self.assertEqual(url_query_parameter("product.html?id=", "id"),
                         None)
        self.assertEqual(url_query_parameter("product.html?id=", "id", keep_blank_values=1),
                         '')

    def test_url_query_parameter_2(self):
        """
        This problem was seen several times in the feeds. Sometime affiliate URLs contains
        nested encoded affiliate URL with direct URL as parameters. For example:
        aff_url1 = 'http://www.tkqlhce.com/click-2590032-10294381?url=http%3A%2F%2Fwww.argos.co.uk%2Fwebapp%2Fwcs%2Fstores%2Fservlet%2FArgosCreateReferral%3FstoreId%3D10001%26langId%3D-1%26referrer%3DCOJUN%26params%3Dadref%253DGarden+and+DIY-%3EGarden+furniture-%3EChildren%26%2339%3Bs+garden+furniture%26referredURL%3Dhttp%3A%2F%2Fwww.argos.co.uk%2Fwebapp%2Fwcs%2Fstores%2Fservlet%2FProductDisplay%253FstoreId%253D10001%2526catalogId%253D1500001501%2526productId%253D1500357023%2526langId%253D-1'
        the typical code to extract needed URL from it is:
        aff_url2 = url_query_parameter(aff_url1, 'url')
        after this aff2_url is:
        'http://www.argos.co.uk/webapp/wcs/stores/servlet/ArgosCreateReferral?storeId=10001&langId=-1&referrer=COJUN&params=adref%3DGarden and DIY->Garden furniture->Children&#39;s gardenfurniture&referredURL=http://www.argos.co.uk/webapp/wcs/stores/servlet/ProductDisplay%3FstoreId%3D10001%26catalogId%3D1500001501%26productId%3D1500357023%26langId%3D-1'
        the direct URL extraction is
        url = url_query_parameter(aff_url2, 'referredURL')
        but this will not work, because aff_url2 contains &#39; (comma sign encoded in the feed)
        and the URL extraction will fail, current workaround was made in the spider,
        just a replace for &#39; to %27
        """
        return # FIXME: this test should pass but currently doesnt
        # correct case
        aff_url1 = "http://www.anrdoezrs.net/click-2590032-10294381?url=http%3A%2F%2Fwww.argos.co.uk%2Fwebapp%2Fwcs%2Fstores%2Fservlet%2FArgosCreateReferral%3FstoreId%3D10001%26langId%3D-1%26referrer%3DCOJUN%26params%3Dadref%253DGarden+and+DIY-%3EGarden+furniture-%3EGarden+table+and+chair+sets%26referredURL%3Dhttp%3A%2F%2Fwww.argos.co.uk%2Fwebapp%2Fwcs%2Fstores%2Fservlet%2FProductDisplay%253FstoreId%253D10001%2526catalogId%253D1500001501%2526productId%253D1500357199%2526langId%253D-1"
        aff_url2 = url_query_parameter(aff_url1, 'url')
        self.assertEqual(aff_url2, "http://www.argos.co.uk/webapp/wcs/stores/servlet/ArgosCreateReferral?storeId=10001&langId=-1&referrer=COJUN&params=adref%3DGarden and DIY->Garden furniture->Garden table and chair sets&referredURL=http://www.argos.co.uk/webapp/wcs/stores/servlet/ProductDisplay%3FstoreId%3D10001%26catalogId%3D1500001501%26productId%3D1500357199%26langId%3D-1")
        prod_url = url_query_parameter(aff_url2, 'referredURL')
        self.assertEqual(prod_url, "http://www.argos.co.uk/webapp/wcs/stores/servlet/ProductDisplay?storeId=10001&catalogId=1500001501&productId=1500357199&langId=-1")
        # weird case
        aff_url1 = "http://www.tkqlhce.com/click-2590032-10294381?url=http%3A%2F%2Fwww.argos.co.uk%2Fwebapp%2Fwcs%2Fstores%2Fservlet%2FArgosCreateReferral%3FstoreId%3D10001%26langId%3D-1%26referrer%3DCOJUN%26params%3Dadref%253DGarden+and+DIY-%3EGarden+furniture-%3EChildren%26%2339%3Bs+garden+furniture%26referredURL%3Dhttp%3A%2F%2Fwww.argos.co.uk%2Fwebapp%2Fwcs%2Fstores%2Fservlet%2FProductDisplay%253FstoreId%253D10001%2526catalogId%253D1500001501%2526productId%253D1500357023%2526langId%253D-1"
        aff_url2 = url_query_parameter(aff_url1, 'url')
        self.assertEqual(aff_url2, "http://www.argos.co.uk/webapp/wcs/stores/servlet/ArgosCreateReferral?storeId=10001&langId=-1&referrer=COJUN&params=adref%3DGarden and DIY->Garden furniture->Children&#39;s garden furniture&referredURL=http://www.argos.co.uk/webapp/wcs/stores/servlet/ProductDisplay%3FstoreId%3D10001%26catalogId%3D1500001501%26productId%3D1500357023%26langId%3D-1")
        prod_url = url_query_parameter(aff_url2, 'referredURL')
        # fails, prod_url is None now
        self.assertEqual(prod_url, "http://www.argos.co.uk/webapp/wcs/stores/servlet/ProductDisplay?storeId=10001&catalogId=1500001501&productId=1500357023&langId=-1")

    def test_add_or_replace_parameter(self):
        url = 'http://domain/test'
        self.assertEqual(add_or_replace_parameter(url, 'arg', 'v'),
                         'http://domain/test?arg=v')
        url = 'http://domain/test?arg1=v1&arg2=v2&arg3=v3'
        self.assertEqual(add_or_replace_parameter(url, 'arg4', 'v4'),
                         'http://domain/test?arg1=v1&arg2=v2&arg3=v3&arg4=v4')
        self.assertEqual(add_or_replace_parameter(url, 'arg3', 'nv3'),
                         'http://domain/test?arg1=v1&arg2=v2&arg3=nv3')
        url = 'http://domain/test?arg1=v1'
        self.assertEqual(add_or_replace_parameter(url, 'arg2', 'v2', sep=';'),
                         'http://domain/test?arg1=v1;arg2=v2')
        self.assertEqual(add_or_replace_parameter("http://domain/moreInfo.asp?prodID=", 'prodID', '20'),
                         'http://domain/moreInfo.asp?prodID=20')
        url = 'http://rmc-offers.co.uk/productlist.asp?BCat=2%2C60&CatID=60'
        self.assertEqual(add_or_replace_parameter(url, 'BCat', 'newvalue', url_is_quoted=True),
                         'http://rmc-offers.co.uk/productlist.asp?BCat=newvalue&CatID=60')
        url = 'http://rmc-offers.co.uk/productlist.asp?BCat=2,60&CatID=60'
        self.assertEqual(add_or_replace_parameter(url, 'BCat', 'newvalue'),
                         'http://rmc-offers.co.uk/productlist.asp?BCat=newvalue&CatID=60')
        url = 'http://rmc-offers.co.uk/productlist.asp?'
        self.assertEqual(add_or_replace_parameter(url, 'BCat', 'newvalue'),
                         'http://rmc-offers.co.uk/productlist.asp?BCat=newvalue')

    def test_url_query_cleaner(self):
        self.assertEqual('product.html?id=200',
                url_query_cleaner("product.html?id=200&foo=bar&name=wired", ['id']))
        self.assertEqual('product.html?id=200',
                url_query_cleaner("product.html?&id=200&&foo=bar&name=wired", ['id']))
        self.assertEqual('product.html',
                url_query_cleaner("product.html?foo=bar&name=wired", ['id']))
        self.assertEqual('product.html?id=200&name=wired',
                url_query_cleaner("product.html?id=200&foo=bar&name=wired", ['id', 'name']))
        self.assertEqual('product.html?id',
                url_query_cleaner("product.html?id&other=3&novalue=", ['id']))
        self.assertEqual('product.html?d=1&d=2&d=3',
                url_query_cleaner("product.html?d=1&e=b&d=2&d=3&other=other", ['d'], unique=False))
        self.assertEqual('product.html?id=200&foo=bar',
                url_query_cleaner("product.html?id=200&foo=bar&name=wired#id20", ['id', 'foo']))
        self.assertEqual('product.html?foo=bar&name=wired',
                url_query_cleaner("product.html?id=200&foo=bar&name=wired", ['id'], remove=True))
        self.assertEqual('product.html?name=wired',
                url_query_cleaner("product.html?id=2&foo=bar&name=wired", ['id', 'foo'], remove=True))
        self.assertEqual('product.html?foo=bar&name=wired',
                url_query_cleaner("product.html?id=2&foo=bar&name=wired", ['id', 'footo'], remove=True))

    def test_path_to_file_uri(self):
        if os.name == 'nt':
            self.assertEqual(path_to_file_uri("C:\\windows\clock.avi"),
                             "file:///C:/windows/clock.avi")
        else:
            self.assertEqual(path_to_file_uri("/some/path.txt"),
                             "file:///some/path.txt")

        fn = "test.txt"
        x = path_to_file_uri(fn)
        self.assert_(x.startswith('file:///'))
        self.assertEqual(file_uri_to_path(x).lower(), os.path.abspath(fn).lower())

    def test_file_uri_to_path(self):
        if os.name == 'nt':
            self.assertEqual(file_uri_to_path("file:///C:/windows/clock.avi"),
                             "C:\\windows\clock.avi")
            uri = "file:///C:/windows/clock.avi"
            uri2 = path_to_file_uri(file_uri_to_path(uri))
            self.assertEqual(uri, uri2)
        else:
            self.assertEqual(file_uri_to_path("file:///path/to/test.txt"),
                             "/path/to/test.txt")
            self.assertEqual(file_uri_to_path("/path/to/test.txt"),
                             "/path/to/test.txt")
            uri = "file:///path/to/test.txt"
            uri2 = path_to_file_uri(file_uri_to_path(uri))
            self.assertEqual(uri, uri2)

        self.assertEqual(file_uri_to_path("test.txt"),
                         "test.txt")

    def test_any_to_uri(self):
        if os.name == 'nt':
            self.assertEqual(any_to_uri("C:\\windows\clock.avi"),
                             "file:///C:/windows/clock.avi")
        else:
            self.assertEqual(any_to_uri("/some/path.txt"),
                             "file:///some/path.txt")
        self.assertEqual(any_to_uri("file:///some/path.txt"),
                         "file:///some/path.txt")
        self.assertEqual(any_to_uri("http://www.example.com/some/path.txt"),
                         "http://www.example.com/some/path.txt")


if __name__ == "__main__":
    unittest.main()

