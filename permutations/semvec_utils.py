"""Some methods to work with pre-existing Semantic Vectors spaces"""

import struct
import copy
from typing import List
import numpy as np
from bitarray import bitarray

def getvector(wordvecs,term):
    """
    Retrieve the vector for a term
    Parameters are a pair of lists, wordvecs[0] - the terms, wordvecs[1] - the vectors
    """
    if term in wordvecs[0]:
        index = wordvecs[0].index(term)
        return wordvecs[1][index]
    else:
        return None

def get_k_vec_neighbors(vectors, query_term, k):
    """Returns the nearest neighboring terms to query_term - a term."""
    query_vec = getvector(vectors,query_term)
    return get_k_neighbors(vectors, query_vec, k)

def get_k_neighbors(vectors, query_vec, k):
    """Returns the nearest neighboring terms to query_vec - a real vector"""
    results=[]
    sims = np.matmul(vectors[1], query_vec)
    indices = np.argpartition(sims, -k)[-k:]
    indices = sorted(indices, key=lambda i: sims[i], reverse=True)
    for index in indices:
        label=vectors[0][index]
        results.append([sims[index],label])
    return results


def get_k_bvec_neighbors(bwordvectors, query_term, k):
    """Returns the nearest neighboring terms (binary vector reps) to query_term - a term"""
    if query_term in bwordvectors[0]:
        query_index = bwordvectors[0].index(query_term)
        query_vec = bwordvectors[1][query_index]
        return get_k_b_neighbors(bwordvectors, query_vec, k)
    else:
        return None


def get_k_b_neighbors(bwordvectors, query_vec, k):
    """Returns the nearest neighboring to terms to query_vec - a binary vector."""
    sims = []
    for vector in bwordvectors[1]:
        nnhd = measure_overlap(query_vec, vector)
        sims.append(nnhd)
    indices = np.argpartition(sims, -k)[-k:]
    indices = sorted(indices, key=lambda i: sims[i], reverse=True)
    results = []
    for index in indices:
        results.append([sims[index],bwordvectors[0][index]])
    return results


def compare_terms_batch(elemental_vectors, semantic_vectors, predicate_vectors, terms) -> List[float]:
    """
    Compares the terms in the specified list of term comparisons.
    :param elemental_vectors:
    :param semantic_vectors:
    :param predicate_vectors:
    :param terms: List of terms to compare. Each line should contain a single string containing exactly one pipe (|) character. Bound products (*) are allowed.
    :return:
    """
    similarities = list()
    for term in terms:
        if term.count("|") is not 1:
            raise ValueError("Input must contain exactly one | character per line")
        term1, term2 = tuple(term.split("|"))
        similarities.append(compare_terms(elemental_vectors, semantic_vectors, predicate_vectors, term1, term2))
    return similarities


def compare_terms(elemental_vectors, semantic_vectors, predicate_vectors,
                  term1: str, term2: str, search_type: str = "boundproduct") -> float:
    """
    Look up the vector representations for the two given terms and determine the similarity between them.
    :param elemental_vectors:
    :param semantic_vectors:
    :param predicate_vectors:
    :param term1: First word or term for comparison.
    :param term2: Second word or term for comparison
    :param search_type: Search type. Currently, only boundproduct is supported.
    :return: Similarity (normalized hamming distance) between the vectors for the two terms.
    """
    if search_type is not "boundproduct":
        raise NotImplementedError()

    return measure_overlap(
        get_bound_product_query_vector_from_string(elemental_vectors, semantic_vectors, predicate_vectors, term1),
        get_bound_product_query_vector_from_string(elemental_vectors, semantic_vectors, predicate_vectors, term2))


def measure_overlap(vector1, vector2, binary: bool = True) -> float:
    """
    Returns the similarity (0.5-normalized hamming distance) between the two given vectors.
    :param vector1: A vector
    :param vector2: A vector
    :param binary: True if the vectors to be compared are binary vectors.
    :return: Similarity. Higher number means more similarity. 1.0 means the vectors are identical. Can be negative.
    """
    if not binary:
        raise NotImplementedError()

    vec2 = copy.copy(vector2)
    vec2 ^= vector1
    # .5 - normalized hamming distance
    nnhd = 2 * (.5 * len(vec2) - vec2.count(True)) / len(vec2)
    return nnhd


def get_vector_for_token(elemental_vectors, semantic_vectors, predicate_vectors,
                         token: str) -> bitarray:
    """
    :param elemental_vectors:
    :param semantic_vectors:
    :param predicate_vectors:
    :param token: A string token such as P(side_effect) or S(drug). More complex expressions are not currently supported
    :return:
    """
    if token[0] == "P":
        vectors = predicate_vectors
    elif token[0] == "E" or token[0] == "C":
        vectors = elemental_vectors
    elif token[0] == "S":
        vectors = semantic_vectors
    else:
        raise MalformedQueryError("Vector set identifier must be P, E, or S (was", token[0], ")")

    token = token[2:-1]
    if token not in vectors[0]:
        raise TermNotFoundError(token)

    query_index = vectors[0].index(token)
    return vectors[1][query_index]


def get_bound_product_query_vector_from_string(elemental_vectors, semantic_vectors, predicate_vectors,
                                               query: str) -> bitarray:
    """
    :param elemental_vectors:
    :param semantic_vectors:
    :param predicate_vectors:
    :param query: calculate the bound product of the terms to be bound in this query. E.g. a query of E(south_africa)*S(pretoria) would result in the elemental vector for South Africa and the semantic vector for Pretoria being looked up; then their bound product is returned.
    :return: Vector for the specified query term.
    """
    if "|" in query:
        raise NotImplementedError()

    if "+" in query:
        raise NotImplementedError()

    result = None
    tokens = query.split("*")
    for token in tokens:
        v = copy.copy(get_vector_for_token(elemental_vectors, semantic_vectors, predicate_vectors, token))
        if result is None:
            result = v
        else:
            result ^= v
    return result


class TermNotFoundError(ValueError):
    def __init__(self, term: str, *args: object) -> None:
        super().__init__("Term not found:", term)


class MalformedQueryError(ValueError):
    def __init__(self, query: str, *args: object) -> None:
        super().__init__("Not a valid query:", query)


def readfile(fileName):
    """Read in a Semantic Vectors binary (.bin) file - currently works for real vector, binary vector and permutation stores"""
    words = []
    vectors = []

    with open(fileName, mode='rb') as file:  # b is important -> binary
        fileContent = file.read(1)

        # determine length of header string (the first byte)
        x = fileContent
        ct = int.from_bytes(x, byteorder='little', signed=False)
        fileContent = file.read(ct)
        header = fileContent.decode().split(" ")
        vindex = header.index('-vectortype')
        vectortype = header[vindex + 1]
        dindex = header.index('-dimension')
        dimension = int(header[dindex + 1])
        unitsize = 4  # bytes per vector dimension
        print(dimension, " ", vectortype)
        if vectortype == 'REAL':
            dimstring = '>' + str(dimension) + 'f'
        elif vectortype == 'PERMUTATION':
            dimstring = '>' + str(dimension) + 'i'
        elif vectortype == 'BINARY':
            unitsize = .125

        skipcount = 0
        count = 0

        fileContent = file.read(1)
        while fileContent:
            # y = int.from_bytes(fileContent[ct:ct + 1], byteorder='little', signed=False)

            # Read Lucene's vInt - if the most significant bit
            # is set, read another byte as significant bits
            # ahead of the seven remaining bits of the original byte
            # Confused? - see vInt at https://lucene.apache.org/core/3_5_0/fileformats.html

            y = int.from_bytes(fileContent, byteorder='little', signed=False)
            binstring1 = format(y, "b")
            if len(binstring1) == 8:
                fileContent = file.read(1)
                y2 = int.from_bytes(fileContent, byteorder='little', signed=False)
                binstring2 = format(y2, "b")
                y = int(binstring2 + binstring1[1:], 2)

            fileContent = file.read(y)
            words.append(fileContent.decode())
            fileContent = file.read(int(unitsize * dimension))

            if vectortype == 'BINARY':
                q=bitarray()
                q.frombytes(fileContent)
            else:
                q = struct.unpack(dimstring, fileContent)

            vectors.append(q)
            fileContent = file.read(1)

    return (words, vectors)

