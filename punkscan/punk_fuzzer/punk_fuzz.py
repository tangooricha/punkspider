#!/usr/bin/env python

# Created by Hyperion Gray, LLC
# Released under the Apache 2.0 License

from urlparse import urlparse
from urlparse import urlunparse
from urlparse import parse_qs
from urllib import urlencode
from urllib import quote_plus
import os
import sys
from random import randint
cwdir = os.path.dirname(__file__)

#for local imports
sys.path.append(os.path.join(cwdir,  "fuzzer_config"))
sys.path.append(os.path.join(cwdir,  "beautifulsoup"))

#for distributed imports
sys.path.append(cwdir)

#import the modules aded to the path
import traceback
import fuzz_config_parser
from multiprocessing import TimeoutError
from multiprocessing.pool import ThreadPool
import requests
from requests.exceptions import ConnectionError
from bs4 import BeautifulSoup

class GenFuzz:
    '''Series of methods useful in the individual fuzzing objects. Note this
    class is built to fuzz a single URL-parameter pair.'''

    def __init__(self):
        '''Grab the various raw fuzzer payloads '''

        self.fuzz_config = fuzz_config_parser.ConfigO()
        self.xss_payloads_raw = self.fuzz_config.get_xss_strings()
        self.sqli_payloads_raw = self.fuzz_config.get_sqli_strings()
        self.bsqli_payloads_raw = self.fuzz_config.get_bsqli_strings()
        self.trav_payloads_raw = self.fuzz_config.get_trav_strings()
        self.xpathi_payloads_raw = self.fuzz_config.get_xpathi_strings()
        self.mxi_payloads_raw = self.fuzz_config.get_mxi_strings()
        self.osci_payloads_raw = self.fuzz_config.get_osci_strings()

        self.pagesize_limit = self.fuzz_config.get_pagesize_limit()
        #self.contentl_requirement = self.fuzz_config.get_contentl_check()
        #self.content_type_requirement = self.fuzz_config.get_content_type_check()
        self.content_type_fallback_requirement = self.fuzz_config.get_contentl_check_wfallback()
        self.allowed_content_types = self.fuzz_config.get_allowed_content_types()
        self.page_memory_load_limit = self.fuzz_config.get_page_memory_load_limit()
        self.proxy = self.fuzz_config.get_proxies_dic()
        self.timeout = 4
        self.hard_timeout = int(self.fuzz_config.get_item('fuzz_configs/hard_timeout'))

    def mutate_append(self, payload_list, str_to_append):
        '''Take in a list of strings to append to the payloads,
        append to the list and return all values as a list'''

        mutated_list = []
        for payload in payload_list:

            appended_payload = payload + str_to_append
            mutated_list.append(appended_payload)

        full_list = mutated_list + payload_list

        return full_list

    def pnk_request_raw(self, url):
        r = requests.get(url, proxies=self.proxy, timeout=int(self.timeout))
        return r

    def pnk_request(self, url):
    
        pool = ThreadPool(processes = 1)
        async_result = pool.apply_async(self.pnk_request_raw, (url,))
    
        try:
            ret_val = async_result.get(timeout = self.hard_timeout)
        except TimeoutError as te:
            traceback.print_exc()
            #raise requests ConnectionError for easier handling if there's a hard timeout
            raise ConnectionError("Request received a hard timeout")
    
        return ret_val
            
    def mutate_prepend(self, payload_list, str_to_prepend):
        '''Take in a list of strings to prepend to the payloads,
        apppend to the list and return all values as a list'''

        mutated_list = []
        for payload in payload_list:

            prepended_payload = str_to_prepend + payload
            mutated_list.append(prepended_payload)

        full_list = mutated_list + payload_list

        return full_list

    def mutate_replace(self, payload_list, str_to_replace, str_to_replace_with):
        '''Take in a list of strings, add values where str_to_replace for
        items in the list are replaced with str_to_replace_with and return a list.'''

        mutated_list = []
        for payload in payload_list:

            payload_replaced = payload.replace(str_to_replace, str_to_replace_with)
            if payload_replaced != payload_list:

                mutated_list.append(payload_replaced)

        full_list = mutated_list + payload_list

        return full_list

    def mutate_replace_char_from_end(self, payload_list, str_to_replace, str_to_replace_with, occurrences_to_replace):
        '''Replaces str_to_replace with str_to_replace_with starting at the end of a string
        and working its way backwards. Replaces a total of occurrences_to_replace characters.
        Note that unlike some of the other utate classes this does not append to and return the full
        list, this only returns the mutated list.'''

        mutated_list = []
        for payload in payload_list:

            payload_spl = payload.rsplit(str_to_replace, occurrences_to_replace)
            payload_new = str_to_replace_with.join(payload_spl)
            mutated_list.append(payload_new)

        return mutated_list

    def mutate_urlencode(self, list_to_enc):
        '''Take in a list of strings to add URL encoded payloads to,
        appends to and returns list taken in. Note the way that
        we are doing requests, this will end up double-url encoding
        before the web server receives the info'''

        list_to_enc_copy = list(list_to_enc)
        list_enc = [quote_plus(x) for x in list_to_enc_copy]

        full_list = list_to_enc_copy + list_enc

        return full_list

    def mutate_urlencode_single(self, str_to_enc):
        '''URL Encode a single string. This is used for any on-the-fly
        encoding needed in fuzzer modules.'''

        return quote_plus(str_to_enc)

    def check_if_param(self, url):
        '''Check if a URL has parameters, if it does return true, if not return false.'''

        if not url.query:
            return False

        else:
            return True

    def set_target(self, url, param):
        '''Set the target url-parameter pair'''

        self.url = url
        self.param = param
        
        #attempt to parse the URL and query parameters
        #if unable to an exception is raised
        
        try:
            
            self.url_parsed = urlparse(self.url)
            self.protocol = self.url_parsed.scheme
            self.query_dic = parse_qs(self.url_parsed.query)
            valid_query_val = self.query_dic[self.param][0]

            #replace the wildcards in the fuzzer config with useful values
            self.__interpret_payloads(valid_query_val)

            return self.url_parsed

        except:
            
            traceback.print_exc()
            raise Exception("Cannot parse url %s" % self.url)

    def __interpret_payloads(self, valid_query_val):
        '''Generates our final payloads, replacing wildcard characters
        in the config with useful values.'''

        self.random_int = randint(1,30000)

        self.xss_payloads = [x.replace("__VALID_PARAM__", valid_query_val).replace("__RANDOM_INT__", str(self.random_int)) for x in self.xss_payloads_raw]
        self.sqli_payloads = [x.replace("__VALID_PARAM__", valid_query_val).replace("__RANDOM_INT__", str(self.random_int)) for x in self.sqli_payloads_raw]
        self.bsqli_payloads = [x.replace("__VALID_PARAM__", valid_query_val).replace("__RANDOM_INT__", str(self.random_int)) for x in self.bsqli_payloads_raw]
        self.trav_payloads = [x.replace("__VALID_PARAM__", valid_query_val).replace("__RANDOM_INT__", str(self.random_int)) for x in self.trav_payloads_raw]
        self.mxi_payloads = [x.replace("__VALID_PARAM__", valid_query_val).replace("__RANDOM_INT__", str(self.random_int)) for x in self.mxi_payloads_raw]
        self.xpathi_payloads = [x.replace("__VALID_PARAM__", valid_query_val).replace("__RANDOM_INT__", str(self.random_int)) for x in self.xpathi_payloads_raw]
        self.osci_payloads = [x.replace("__VALID_PARAM__", valid_query_val).replace("__RANDOM_INT__", str(self.random_int)) for x in self.osci_payloads_raw]

    def replace_param(self, replacement_string):
        '''Replace a parameter in a url with another string. Returns
        a fully reassembled url as a string.'''
        
        self.query_dic[self.param] = replacement_string

        #this incidentally will also automatically url-encode the payload (thanks urlencode!)
        query_reassembled = urlencode(self.query_dic, doseq = True)

        #3rd element is always the query, replace query with our own

        url_list_parsed = list(self.url_parsed)
        url_list_parsed[4] = query_reassembled
        url_parsed_q_replaced = tuple(url_list_parsed)
        url_reassembled = urlunparse(url_parsed_q_replaced)

        return url_reassembled

    def generate_urls_gen(self, final_payload_list):
        '''Take in a list of payloads and returns a generator of
        (urls with fuzz values, payload) tuples from a list of payloads.'''
        
        for payload in final_payload_list:
            
            fuzzy_url = self.replace_param(payload)
            yield (fuzzy_url, payload)

    def url_response_gen(self, url_gen):
        '''Take in a (url with fuzz values, payload) generator and returns a (url,
        payload, response) tuple generator. Most commonly takes in a generator from
        the generate_urls_gen method.'''

        for url_payload in url_gen():

            url = url_payload[0]
            payload = url_payload[1]

            try:
                r = self.pnk_request(url)
                ret_text = r.text

            except:
                traceback.print_exc()
                ret_text = "The request timed out"

            yield (url, payload, ret_text)

    def generate_url(self, payload):
        '''Take in a single payload as a string, and returns a single
        (url with fuzz value, payload) tuple.'''

        fuzzy_url = self.replace_param(payload)

        return (fuzzy_url, payload)

    def url_response(self, url_payload):
        '''Take in a single (url with fuzz value, payload) tuple and
        returns a (payload, URL response) tuple'''

        url = url_payload[0]
        payload = url_payload[1]
        
        try:

            r = self.pnk_request(url)
            ret_text = r.text

        except:
            traceback.print_exc()
            ret_text = "The request timed out"

        return (url, payload, ret_text)

    def check_stability(self, url_payload, diff_allowed = 10):

        r_1 = self.url_response(url_payload)[2]
        r_2 = self.url_response(url_payload)[2]

        r_2_lower_bound = len(r_2) - diff_allowed
        r_2_upper_bound = len(r_2) + diff_allowed

        #if URL appears unstable (different content lengths, same request) or request times out return False
        if len(r_1) < r_2_lower_bound or len(r_1) > r_2_upper_bound or r_1 == "The request timed out" or r_2 == "The request timed out":
            return False

        else:

            return True

    def search_urls_tag(self, url_response_gen, match_list, vuln_type, tag = False, attribute = False):
        '''Take in a (url, payload, response text) generator and returns a list
        of (url, payload, vuln_type) that appear to be vulnerable through a string match
        either from text in a tag or text in an attribute or both.'''

        if not tag and not attribute:
            
            raise Exception("Neither tag nor attribute are set")

        vulnerable_url_list = []
        for url_response in url_response_gen:

            url_payload_info = (url_response[0], url_response[1], vuln_type, self.param, self.protocol)

            # if size of site is too big, don't load to memory w/ bsoup - return 0 XSS bugs
            if sys.getsizeof(url_response[2]) > self.page_memory_load_limit:
                return []

            #parse the response text            
            try:
                soup = BeautifulSoup(url_response[2])

            #! if we can't parse it, return no vulnerabilities for now
            except:
                return []

            for tag_in_page in soup.find_all(tag):

                for match_string in match_list:

                    #if tag is set, look in the tag's string
                    if tag:
                        tag_string = tag_in_page.string

                        if tag_string and match_string in tag_string:

                            #if we find a vuln, stop
                            vulnerable_url_list.append(url_payload_info)
                            return vulnerable_url_list

                    #if attribute is set, look in the attribute's string
                    if attribute:
                        attribute_string = tag_in_page.get(attribute)

                        if attribute_string and match_string in attribute_string:

                            #if we find a vuln, stop
                            vulnerable_url_list.append(url_payload_info)
                            return vulnerable_url_list

        return vulnerable_url_list

    def search_responses(self, url_response_gen, match_list, vuln_type):
        '''Take in a (url, payload, response text), search for a matching string anywhere on the page w/out parsing.
        Note we .lower() the response, so don\'t search with any capital letters. Takes a list of strings to match.
        Also requires the vulnerability type if a match is found.'''

        vulnerable_url_list = []

        for url_response in url_response_gen:

            url_payload_info = (url_response[0], url_response[1], vuln_type, self.param, self.protocol)
            response_text = url_response[2]

            for match_string in match_list:

                if match_string in response_text.lower():

                    vulnerable_url_list.append(url_payload_info)

                    return vulnerable_url_list

        return vulnerable_url_list

    def compare_response_length(self, url_response, content_length_one, content_length_two, difference, vuln_type):
        '''If content length is greater than content length two + difference report back a vulnerability.
        Currently used for blind sql where true sql statement is content one and false sql statement is two. In
        other words we are hoping to find content length one to be larger due to a true sql statement being injected.
        url_response is a (url, payload, response text) from either one, this tuple is only used for url tracking 
        purposes in this case. Now checks if a URL is stable before returning a vulnerability'''

        if content_length_one > content_length_two + 10:

            vulnerability = (url_response[0], url_response[1], vuln_type, self.param, self.protocol)
            return vulnerability

        else:
            return False

    def get_head(self):

        try:
            head = requests.head(self.url, proxies = self.proxy, timeout = self.timeout).headers
            return head
            
        except:
            return False        

    def fuzzworth_content_type(self, head, allowed_types_lst, full_req_match = False, strict = False):

        if head and "content-type" in head:
            content_type = head["content-type"]

            for allowed_type in allowed_types_lst:

                #if strict checking is turned on
                if full_req_match:

                    #if allowed type is content-type return true
                    if allowed_type == content_type:
                        return True

                else:
                    #if the allowed type is part of the content-type return true
                    if allowed_type in content_type:
                        return True

            #if nothing returned true return false
            return False            

        else:

            if strict:
                return False 

            else:
                return True

    def fuzzworth_contentl(self, head, strict = False):
        '''Check the content-length before moving on. If strict is set to True content-length
        must be validated before moving on. If strict is set to False (default) the URL will
        be fuzzed if no content-length is found or no head is returned. The idea behind this
        method is to ensure that huge files are not downloaded, slowing down fuzzing.'''
        
        #no param no fuzzing
        if head and "content-length" in head:
          
            content_length = int(head["content-length"])
            
            if content_length < self.pagesize_limit:
                return True

            else:
                return False

        else:
            if strict:
                return False

            else:
                return True

    def fuzzworth_contentl_with_type_fallback(self, head, allowed_types_lst, full_req_match = False):
        '''This method will check the content length header strictly. If a content-length header is found
        and the content-length is below a certain amount (set in the fuzzer config) return True if either of those
        is not satisfied,. If it is not check the content-type, if the content-type is of a certain type return 
        True. If not or if content-type can't be read either, return False.'''

        #if content-length header is found return True
        if head and "content-length" in head:
            return self.fuzzworth_contentl(head, strict = True)
        
        #if content-length header not found, check content-type, if it is of allowed type
        #return True, otherwise false
        if head and "content-type" in head:
            return self.fuzzworth_content_type(head, allowed_types_lst, full_req_match = False, strict = True)
            
        return False

class XSSFuzz(GenFuzz):
    '''This class fuzzes a single URL-parameter pair with a simple xss fuzzer'''

    def __init__(self):

        GenFuzz.__init__(self)

    def xss_set_target(self, url, param):
        '''Set the target'''
        
        self.target = self.set_target(url, param)

    def __xss_make_payloads(self):
        '''Set various mutations for xss payloads'''

        #mutate payloads
        xss_string_list_add_mut_prep = self.mutate_prepend(self.xss_payloads, '">')
        xss_string_list_add_enc = self.mutate_urlencode(xss_string_list_add_mut_prep)
        final_list = self.mutate_replace(xss_string_list_add_enc, '"', "'")

        #return list of all payloads
        return final_list
        
    def __xss_url_gen(self):
        '''Yield URLs that are to be XSS requests'''

        return self.generate_urls_gen(self.__xss_make_payloads())

    def __xss_get_url_responses(self):
        '''Yield responses - takes in a url generator and outputs
        a response generator'''

        return self.url_response_gen(self.__xss_url_gen)

    def xss_fuzz(self):
        '''Returns a list of (vulnerable url, payload) tuples
        of vuln type "xss"'''

        return self.search_urls_tag(self.__xss_get_url_responses(),  ["alert(%s)" % self.random_int], "xss", tag="script")

class SQLiFuzz(GenFuzz):
    '''This class is an error-based sql injection fuzzer '''

    def __init__(self):

        GenFuzz.__init__(self)

    def sqli_set_target(self, url, param):
        '''Set the target '''

        self.target = self.set_target(url, param)

    def __sqli_make_payloads(self):
        '''Set various mutations for SQL Injection'''

        #mutate payloads
        sqli_string_list_add_mut_append = self.mutate_append(self.sqli_payloads, ')')
        sqli_string_list_add_enc = self.mutate_urlencode(sqli_string_list_add_mut_append)
        final_list = sqli_string_list_add_enc

        #return final list of payloads
        return final_list

    def __sqli_url_gen(self):
        '''Yield URLs that are to be SQLi requests'''

        return self.generate_urls_gen(self.__sqli_make_payloads())

    def __sqli_get_url_responses(self):
        '''Yield responses - takes in a url generator and outputs
        a response generator'''

        return self.url_response_gen(self.__sqli_url_gen)

    def sqli_fuzz(self):
        '''Returns a list of (vulnerable url, payload) tuples
        of vuln type "sqli"'''

        #define what we're looking for on the pages

        match_list_raw = ["you have an error in your sql syntax",
        "supplied argument is not a valid mysql",
        "[microsoft][odbc microsoft acess driver]",
        "[microsoft][odbc sql server driver]",
        "microsoft ole db provider for odbc drivers",
        "java.sql.sqlexception: syntax error or access violation",
        "postgresql query failed: error: parser:",
        "db2 sql error:",
        "dynamic sql error",
        "sybase message:",
        "ora-01756: quoted string not properly terminated",
        "ora-00933: sql command not properly ended",
        "pls-00306: wrong number or types",
        "incorrect syntax near",
        "unclosed quotation mark before",
        "syntax error containing the varchar value",
        "ora-01722: invalid number",
        "ora-01858: a non-numeric character was found where a numeric was expected",
        "ora-00920: invalid relational operator",
        "ora-00920: missing right parenthesis"]

        #we lower our http responses for easier matching
        match_list = [x.lower() for x in match_list_raw]
        
        url_response_gen = self.__sqli_get_url_responses()
        return self.search_responses(url_response_gen, match_list, "sqli")

class TravFuzz(GenFuzz):
    '''This class is a path traversal fuzzer '''

    def __init__(self):

        GenFuzz.__init__(self)

    def trav_set_target(self, url, param):
        '''Set the target '''

        self.target = self.set_target(url, param)

    def __trav_make_payloads(self):
        '''Set various mutations for SQL Injection'''

        #mutate payloads
        trav_string_list_add_enc = self.mutate_urlencode(self.trav_payloads)
        final_list = trav_string_list_add_enc

        #return final list of payloads
        return final_list

    def __trav_url_gen(self):
        '''Yield URLs that are to be SQLi requests'''

        return self.generate_urls_gen(self.__trav_make_payloads())

    def __trav_get_url_responses(self):
        '''Yield responses - takes in a url generator and outputs
        a response generator'''

        return self.url_response_gen(self.__trav_url_gen)

    def trav_fuzz(self):
        '''Returns a list of (vulnerable url, payload) tuples
        of vuln type "trav"'''

        #define what we're looking for on the pages

        match_list_raw = ["root:x:", "[font]"]

        #we lower our http responses for easier matching
        match_list = [x.lower() for x in match_list_raw]

        url_response_gen = self.__trav_get_url_responses()
        return self.search_responses(url_response_gen, match_list, "trav")

class MXiFuzz(GenFuzz):
    '''This class is an MX Injection fuzzer '''

    def __init__(self):

        GenFuzz.__init__(self)

    def mxi_set_target(self, url, param):
        '''Set the target '''

        self.target = self.set_target(url, param)

    def __mxi_make_payloads(self):
        '''Set various mutations for mx Injection'''

        #mutate payloads
        mxi_string_list_add_enc = self.mutate_urlencode(self.mxi_payloads)
        final_list = mxi_string_list_add_enc

        #return final list of payloads
        return final_list

    def __mxi_url_gen(self):
        '''Yield URLs that are to be mxi requests'''

        return self.generate_urls_gen(self.__mxi_make_payloads())

    def __mxi_get_url_responses(self):
        '''Yield responses - takes in a url generator and outputs
        a response generator'''

        return self.url_response_gen(self.__mxi_url_gen)

    def mxi_fuzz(self):
        '''Returns a list of (vulnerable url, payload) tuples
        of vuln type "mxi"'''
        
        print "mxi fuzz"

        #define what we're looking for on the pages

        match_list_raw = ["unexpected extra arguments to select", 
                      "Bad or malformed request", "Could not access the following folders",
                      "invalid mailbox name", 
                      "go to the folders page"]

        #we lower our http responses for easier matching
        match_list = [x.lower() for x in match_list_raw]

        url_response_gen = self.__mxi_get_url_responses()
        return self.search_responses(url_response_gen, match_list, "mxi")

class XPathiFuzz(GenFuzz):
    '''This class is an XPath injection fuzzer '''

    def __init__(self):

        GenFuzz.__init__(self)

    def xpathi_set_target(self, url, param):
        '''Set the target '''

        self.target = self.set_target(url, param)

    def __xpathi_make_payloads(self):
        '''Set various mutations for XPath Injection'''

        #mutate payloads
        xpathi_string_list_add_enc = self.mutate_urlencode(self.xpathi_payloads)
        final_list = xpathi_string_list_add_enc

        #return final list of payloads
        return final_list

    def __xpathi_url_gen(self):
        '''Yield URLs that are to be xpathi requests'''

        return self.generate_urls_gen(self.__xpathi_make_payloads())

    def __xpathi_get_url_responses(self):
        '''Yield responses - takes in a url generator and outputs
        a response generator'''

        return self.url_response_gen(self.__xpathi_url_gen)

    def xpathi_fuzz(self):
        '''Returns a list of (vulnerable url, payload) tuples
        of vuln type "xpathi"'''

        #define what we're looking for on the pages.
        #credit to Andres Riancho/w3af: match list from 
        #https://github.com/andresriancho/w3af/blob/master/plugins/audit/xpath.py
        match_list_raw = ['System.Xml.XPath.XPathException:',
        'MS.Internal.Xml.',
        'Unknown error in XPath',
        'org.apache.xpath.XPath',
        'A closing bracket expected in',
        'An operand in Union Expression does not produce a node-set',
        'Cannot convert expression to a number',
        'Document Axis does not allow any context Location Steps',
        'Empty Path Expression',
        'DOMXPath::'
        'Empty Relative Location Path',
        'Empty Union Expression',
        "Expected ')' in",
        'Expected node test or name specification after axis operator',
        'Incompatible XPath key',
        'Incorrect Variable Binding',
        'libxml2 library function failed',
        'libxml2',
        'xmlsec library function',
        'xmlsec',
        "error '80004005'",
        "A document must contain exactly one root element.",
        '<font face="Arial" size=2>Expression must evaluate to a node-set.',
        "Expected token ']'",
        "<p>msxml4.dll</font>",
        "<p>msxml3.dll</font>",
        '4005 Notes error: Query is not understandable']
        #we lower our http responses for easier matching
        match_list = [x.lower() for x in match_list_raw]

        url_response_gen = self.__xpathi_get_url_responses()
        return self.search_responses(url_response_gen, match_list, "xpathi")

class OSCiFuzz(GenFuzz):
    '''This class is an MX Injection fuzzer '''

    def __init__(self):

        GenFuzz.__init__(self)

    def osci_set_target(self, url, param):
        '''Set the target '''

        self.target = self.set_target(url, param)

    def __osci_make_payloads(self):
        '''Set various mutations for mx Injection'''

        #mutate payloads
        osci_string_list_add_enc = self.mutate_urlencode(self.osci_payloads)
        final_list = osci_string_list_add_enc

        #return final list of payloads
        return final_list

    def __osci_url_gen(self):
        '''Yield URLs that are to be osci requests'''

        return self.generate_urls_gen(self.__osci_make_payloads())

    def __osci_get_url_responses(self):
        '''Yield responses - takes in a url generator and outputs
        a response generator'''

        return self.url_response_gen(self.__osci_url_gen)

    def osci_fuzz(self):
        '''Returns a list of (vulnerable url, payload) tuples
        of vuln type "osci"'''

        #define what we're looking for on the pages

        match_list_raw = ["root:x:", "[font]"]

        #we lower our http responses for easier matching
        match_list = [x.lower() for x in match_list_raw]

        url_response_gen = self.__osci_get_url_responses()
        return self.search_responses(url_response_gen, match_list, "osci")

class BSQLiFuzz(GenFuzz):
    '''Content-length based sql injection checks '''

    def __init__(self):

        GenFuzz.__init__(self)

    def bsqli_set_target(self, url, param):
        '''Set the target '''

        self.target = self.set_target(url, param)

    def __bsqli_make_payloads(self):
        '''Set various mutations for SQL Injection. This is a bit different
        from the previous XSS and SQLi payloads in that we categorize them into true and false.
        So this returns a list of tuples of (true sql payloads, false sql payloads)'''

        #mutate payloads
        #mutate_replace_char_from_end(self, payload_list, str_to_replace, str_to_replace_with, occurrences_to_replace)

        payload_list = []
        for payload in self.bsqli_payloads:

            #(true_sql, false_sql)
            true_sql_payload = payload

            #replace the trailing "1" with a "2" to make it false
            false_sql_payload = self.mutate_replace_char_from_end([payload], "1", "2", 1)[0]

            true_sql_payload_enc = self.mutate_urlencode_single(true_sql_payload)
            false_sql_payload_enc = self.mutate_urlencode_single(false_sql_payload)
            
            payload_list.append((true_sql_payload, false_sql_payload))
            payload_list.append((true_sql_payload_enc, false_sql_payload_enc))

        return payload_list

    def __bsqli_url_gen(self):
        '''Yield URLs that are to be SQLi requests. We continue to keep track of
        true and false url pairs so we can later determine their relative content 
        lengths.'''

        for payload in self.__bsqli_make_payloads():

            true_sql_payload = payload[0]
            false_sql_payload = payload[1]
            
            true_url = self.generate_url(true_sql_payload)
            false_url = self.generate_url(false_sql_payload)
            
            yield (true_url, false_url)

    def bsqli_check_stability(self, url_payload):
    
        return self.check_stability(url_payload)

    def bsqli_fuzz(self):
        '''Perform the fuzzing '''

        vulnerable_url_list = []
        first = 0
        for url_payload in self.__bsqli_url_gen():

            #if not stable, return no vulns, can't reliably determine bsqli. Do only once.
            if first == 0:
                if not self.bsqli_check_stability(url_payload[0]):
                    return []

            if first == 0:
                first = first + 1
            
            true_url_response = self.url_response(url_payload[0])
            false_url_response = self.url_response(url_payload[1])

            content_length_true = len(true_url_response[2])
            content_length_false = len(false_url_response[2])

            vuln_check = self.compare_response_length(true_url_response, content_length_true, content_length_false, 10, "bsqli")

            if vuln_check:
                vulnerable_url_list.append(vuln_check)

                #return as soon as you find a potential vulnerability
                return vulnerable_url_list

        return vulnerable_url_list

class PunkFuzz(GenFuzz):
    '''A utility class that uses all of the fuzzing objects'''

    def __init__(self, mapper_instance = False):
        '''Initialize fuzzing modules'''

        self.gen_fuzz = GenFuzz()
        self.xss_fuzzer = XSSFuzz()
        self.sqli_fuzzer = SQLiFuzz()
        self.bsqli_fuzzer = BSQLiFuzz()
        self.trav_fuzzer = TravFuzz()
        self.mxi_fuzzer = MXiFuzz()
        self.xpathi_fuzzer = XPathiFuzz()
        self.osci_fuzzer = OSCiFuzz()
        self.mapper_instance = mapper_instance

    def punk_set_target(self, url, param):
        '''Set the targets for the fuzzers '''

        self.url = url
        self.param = param
        self.gen_fuzz.set_target(url, param)
        self.xss_fuzzer.xss_set_target(url, param)
        self.sqli_fuzzer.sqli_set_target(url, param)
        self.bsqli_fuzzer.bsqli_set_target(url, param)
        self.trav_fuzzer.trav_set_target(url, param)
        self.mxi_fuzzer.mxi_set_target(url, param)
        self.xpathi_fuzzer.xpathi_set_target(url, param)
        self.osci_fuzzer.osci_set_target(url, param)

    def fuzz(self):
        '''Perform the fuzzes and collect (vulnerable url, payload) tuples '''

        self.head = self.gen_fuzz.get_head()

        #if this returns false, don't check the website
        #it likely has large content and will slow down the fuzz

        if not self.gen_fuzz.fuzzworth_contentl_with_type_fallback(self.head,\
        self.gen_fuzz.allowed_content_types, False):
            return []

        #fuzz if fuzzworth is true, if false skip fuzzing
        if self.mapper_instance:
            self.mapper_instance.set_status(u'Starting XSS fuzz')

        self.xss_fuzz_results = self.xss_fuzzer.xss_fuzz()

        if self.mapper_instance:
            self.mapper_instance.set_status(u'Starting SQLi fuzz')

        self.sqli_fuzz_results = self.sqli_fuzzer.sqli_fuzz()

        if self.mapper_instance:
            self.mapper_instance.set_status(u'Starting bsqli fuzz')

        self.bsqli_fuzz_results = self.bsqli_fuzzer.bsqli_fuzz()
        
        
        if self.mapper_instance:
            self.mapper_instance.set_status(u'Starting trav fuzz')
        
        self.trav_fuzz_results = self.trav_fuzzer.trav_fuzz()

        if self.mapper_instance:
            self.mapper_instance.set_status(u'Starting mxi fuzz')
        
        self.mxi_fuzz_results = self.mxi_fuzzer.mxi_fuzz()        

        if self.mapper_instance:
            self.mapper_instance.set_status(u'Starting xpathi fuzz')
        
        self.xpathi_fuzz_results = self.xpathi_fuzzer.xpathi_fuzz()

        if self.mapper_instance:
            self.mapper_instance.set_status(u'Starting osci fuzz')
        
        self.osci_fuzz_results = self.osci_fuzzer.osci_fuzz()

        if self.mapper_instance:
            self.mapper_instance.set_status(u'Finished fuzzing... collecting results')

        final_results = self.xss_fuzz_results + self.sqli_fuzz_results + self.bsqli_fuzz_results + self.trav_fuzz_results\
        + self.mxi_fuzz_results + self.xpathi_fuzz_results + self.osci_fuzz_results

        return final_results
