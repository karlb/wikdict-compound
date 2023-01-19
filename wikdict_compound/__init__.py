import sqlite3
from pathlib import Path
import statistics
from dataclasses import dataclass, replace
from typing import Optional
from functools import cached_property

from .make_db import make_db

supported_langs = "de en fi nl sv".split()
query_count = 0


DEBUG_QUERY_LOG = False


def get_potential_matches(compound, r, lang):
    match = r["other_written"].lower()
    yield match
    pos_list = r["part_of_speech_list"].split(",")

    if lang == "de":
        if "noun" in pos_list:
            if not match.endswith("s") and compound.startswith(match + "s"):
                yield match + "s"


def find_matches_in_db(db_path, lang, compound: str, ignore_word=None, first_part=True):
    conn = sqlite3.connect(Path(db_path) / f"{lang}-compound.sqlite3")
    conn.row_factory = sqlite3.Row
    global query_count
    query = """
        SELECT *
        FROM (
            SELECT DISTINCT
                other_written,
                length(other_written)*length(other_written) * rel_score AS rel_score,
                affix_type,
                written_rep,
                part_of_speech_list
            FROM compound_splitter
            WHERE (
                (
                    other_written <= :compound
                    AND other_written >= substr(:compound, 1, 2)
                    AND :compound LIKE other_written || '%'
                ) OR (
                    other_written = substr(:compound, 1, 1)
                )
            )
            --WHERE other_written <= :compound AND :compound LIKE other_written || '%'
            --WHERE other_written <= :compound AND other_written || 'z' > :compound
              AND (affix_type IS NULL OR :first_part = (affix_type = "prefix"))

              -- For test data evaluation only. Without this, we could not
              -- split compound words which are in the dictionary themselves.
              AND other_written IS NOT lower(:ignore_word)
              AND written_rep IS NOT lower(:ignore_word)
        )
        ORDER BY rel_score DESC
        LIMIT 3
    """
    bindings = dict(compound=compound, ignore_word=ignore_word, first_part=first_part)
    # if query_count == 0:
    #     print_query_plan(conn, query, bindings)
    result = conn.execute(query, bindings).fetchall()

    query_count += 1
    if DEBUG_QUERY_LOG:
        with open("query.log", "a") as f:
            f.write(compound + "\n")
            for r in result:
                f.write(str(dict(r)) + "\n")

    return result


@dataclass(frozen=True)
class Part:
    written_rep: str
    score: float
    match: str


@dataclass(frozen=True)
class Solution:
    parts: list[Part]

    @cached_property
    def score(self):
        return (
            statistics.geometric_mean(p.score for p in self.parts)
            / len(self.parts) ** 2
        )


@dataclass(frozen=True)
class PartialSolution(Solution):
    compound: str  # full compound which is to be split

    @cached_property
    def score(self):
        if not self.parts:
            return 0
        return super().score * sum(len(p.match) for p in self.parts)


@dataclass
class SplitContext:
    """Context for the process of splitting a compound into all parts."""

    compound: str
    queries: int = 0
    graph_str: str = ""  # graphviz dot format visualization of splitting graph
    best_partial_solution: Optional[PartialSolution] = None
    best_solution: Optional[Solution] = None

    @property
    def graph(self) -> str:
        return "digraph {\n" + self.graph_str + "}\n"


def prune_branch(solution, context) -> bool:
    """Is the current splitting branch unlikely to provide a good result?"""
    best_score = (
        context.best_partial_solution.score if context.best_partial_solution else 0
    )
    if solution.score > best_score:
        context.best_partial_solution = solution
    elif solution.score < 0.1 * best_score:
        return True

    # if context.best_solution and len(solution.parts) == len(
    #     context.best_solution.parts
    # ):
    #     return True

    return False


def split_compound_interal(
    db_path,
    lang: str,
    compound: str,
    context: SplitContext,
    solution: PartialSolution,
    ignore_word=None,
    first_part=False,
    all_results=False,
    rec_depth=0,
    node_name="START",
) -> list[Solution]:
    if prune_branch(solution, context):
        return []

    context.queries += 1
    result = find_matches_in_db(db_path, lang, compound, ignore_word, first_part)
    if not result:
        return []

    solutions = []
    for r in result:
        for match in get_potential_matches(compound, r, lang):
            new_part = Part(r["written_rep"], r["rel_score"], match)
            new_solution = replace(solution, parts=solution.parts + [new_part])
            new_node_name = f'{context.queries}-{r["written_rep"]}'
            context.graph_str += f'\t "{node_name}" -> "{new_node_name}"\n'
            context.graph_str += f'\t "{new_node_name}" [label="{r["written_rep"]}\\n{r["rel_score"]:.2f}\\n{new_solution.score:.2f}"]\n'
            rest = compound.replace(match, "", 1)
            if not rest:
                if r["affix_type"] in [None, "suffix"]:
                    solutions.append(Solution(parts=[new_part]))
                context.graph_str += f'\t "{new_node_name}" [shape=box]\n'
                continue
            recursive_results = split_compound_interal(
                db_path,
                lang,
                rest,
                solution=new_solution,
                context=context,
                rec_depth=rec_depth + 1,
                node_name=new_node_name,
            )
            if not recursive_results:
                continue
            splitted_rest = recursive_results[0].parts
            solutions.append(Solution(parts=[new_part] + splitted_rest))

    if not solutions:
        return []

    solutions.sort(key=lambda s: s.score, reverse=True)

    if context.best_solution and solutions[0].score > context.best_solution.score:
        context.best_solution = solutions[0]

    return solutions


def split_compound(
    db_path,
    lang: str,
    compound: str,
    ignore_word=None,
    all_results=False,
    write_graph_to_file: Optional[str] = None,
):
    compound = compound.lower()
    context = SplitContext(compound=compound)
    results = split_compound_interal(
        db_path,
        lang,
        compound,
        solution=PartialSolution(parts=[], compound=compound),
        ignore_word=ignore_word,
        first_part=True,
        context=context,
    )

    if write_graph_to_file:
        with open(write_graph_to_file, "w") as f:
            f.write(context.graph)

    if all_results:
        return results
    else:
        return results[0] if results else None


def print_query_plan(conn, query, bindings={}):
    depth_of = {0: -1}
    result = conn.execute("EXPLAIN QUERY PLAN " + query, bindings).fetchall()
    for r in result:
        depth = depth_of[r["parent"]] + 1
        depth_of[r["id"]] = depth
        print("|  " * depth + r["detail"])
