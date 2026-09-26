# Pre-exposure family review

This review was completed during benchmark construction, using prior task prompts,
reference answers, fixtures, and family IDs—not new model responses. The machine
report inventories all 852 prior records from the four benchmark task files and
eight dataset splits. B repeats some Stage 2 data; 852 is a record count, not a
count of independent families.

Canonical response schemas, Python syntax, and broad subjects such as callbacks,
mutation, and JSON must recur to measure transfer. The criterion here is a new
problem, algorithm, or interaction—not the absence of every previously seen
language construct. No claim is made that lexical heuristics prove independence.
The following are the final 48 families and the substantive distinctions checked.

| Final family | Novel operation / distinction from prior material |
| --- | --- |
| polynomial_fold | Horner polynomial evaluation, not a sum/filter/running-total exercise. |
| backspace_buffer | Destructive editing with empty-buffer behavior, not deduplication or alternate-letter selection. |
| nested_leaf_addresses | Recursive path construction and hierarchical ordering, not one-level flattening or record totals. |
| cartesian_choices | Cartesian product including empty-product identity, not interleaving/zip. |
| decimal_carry_arrays | Arbitrary-length digit-array addition and carry propagation, not weighted digit sum or digital root. |
| capacity_batching | Variable-weight greedy capacity packing, not fixed-width chunking or stable partition. |
| breadth_first_distance | Shortest directed hop count with cycles, not binary search or simple repository call tracing. |
| independent_grid_rows | Allocation independence while marking a two-dimensional grid, not appending to a copied input list. |
| overlapping_occurrences | All overlapping substring matches and terminal boundary, not first prefix or last-index tracking. |
| boolean_integer_boundary | Exact Python integer type vs bool subclass, not numeric sign filtering. |
| identifier_full_scan | Complete ASCII lexical validation, not name equality or string suffix selection. |
| consecutive_alarm_state | Resettable maximum run length, not last occurrence or global counts. |
| nonlocal_counter_state | Stateful independent nonlocal closure cells; prior closure task concerned loop late binding. |
| nested_shallow_copy | Outer dict independence and shared nested queue in the same trace; not a renamed one-list append/alias snippet. |
| eager_default_argument | Eager setdefault argument evaluation on both hit and miss; distinct from mutable default lifetime. |
| exception_continue_accumulator | Per-record exception handling and continue paths, not try/else or finally overriding return. |
| lazy_source_mutation | Mutation before lazy generator consumption changes yielded values; prior generator task concerned exhaustion. |
| assignment_rhs_snapshot | RHS snapshot combined with left-to-right subscript target evaluation, not starred unpacking alone. |
| zigzag_integer_encoding | Signed-to-unsigned serialization mapping distinguishes opposite signs; not absolute difference or rounding. |
| switch_type_guard | Mixed bool/string normalization requires dispatch before string methods; not boolean negation or empty-list fallback. |
| rook_conflict_scan | Premature safe-row return prevents both later-row and column conflict checks; not deletion of duplicate appends. |
| byte_field_roundtrip | Two-function eight-bit pack/unpack roundtrip with separate hunks, not XOR checksum or single-mask fixes. |
| common_margin_removal | Data-dependent common indentation while preserving relative/trailing spaces; not slugification or global strip. |
| visual_tab_stops | Column-dependent tab expansion with LF resets; not line-ending replacement. |
| uptime_event_pipeline | Decode event states then sum closed active intervals; not max duration or inventory deltas. |
| rational_addition_pipeline | Cross-denominator addition, reduction, sign normalization, zero; prior gcd bug is only a subroutine concept. |
| postfix_operand_pipeline | Mixed token classification and ordered stack operands; not parse-and-average/sum. |
| luhn_payload_pipeline | Position-dependent digit transformation followed by check-digit complement; not XOR or digit product. |
| permission_bit_pipeline | Idempotent OR construction plus all-required mask check; not set membership alone. |
| retry_delay_pipeline | Capped exponential delays plus between-attempt accounting; not range clamp or fee sum. |
| edit_distance_table | Dynamic programming over insert/delete/replace, not anagram or palindrome. |
| dependency_schedule | Repeated lexical ready selection and cycle failure, not arbitrary graph traversal. |
| integer_square_bound | Exact integer floor root with large inputs; not primality or rounding to multiples. |
| dotted_release_order | Numeric component comparison with missing trailing zeros, not string common prefix. |
| wildcard_full_match | Full wildcard language matching with empty-star states, not subsequence. |
| smallest_absent_positive | Missing positive discovery across duplicates and negative values, not range filtering. |
| symbol_scope_query | Regex declaration lookup with nested language/root/generated-file scope and result limit; schema differs substantively from simple symbol-name lookup. |
| read_disjoint_ranges | Ordered disjoint inclusive ranges at a pinned symbolic revision; not one read-span substitution. |
| test_execution_environment | Typed node selection with cwd, environment, timeout and fail-fast semantics; not a renamed suite list. |
| repository_metadata_subset | Field subset plus untracked flag and deliberate omission of optional revision; not queue/catalog requests. |
| diagnostic_severity_filter | Nested severity filtering, grouping, and nullable pagination; not scalar metric emission. |
| ordered_inspection_plan | Heterogeneous nested tool calls and explicit dependency edges; prior plans were action/target or path/mode arrays without this graph. |
| context_suppression_flow | Context-manager exception suppression and continuation across files, not ordinary catch/rethrow. |
| snapshot_unregister_dispatch | Callback removal during a snapshot dispatch affects only subsequent dispatch; not fixed registration order. |
| layered_configuration_deletion | ChainMap deletion exposes fallback while writes affect only first map; not selecting first nonempty config. |
| captured_default_export | Re-exported callable captured in a default vs a replaced module function; prior examples captured scalars/closure factors, not this interaction. |
| cached_property_refresh | Source mutation, stale cache, explicit invalidation and recomputation across modules; not subclass method override. |
| shared_memoized_dependency | Two dependency branches share memo state and miss-trace ordering; not arithmetic call chains alone. |

Three draft patterns (page-count ceiling, duplicate surcharge deletion and a basic subclass/property
example) were discarded before freeze because their relationship to prior families
was too close. This review makes no use of candidate performance on these tasks.

Automated checks compare exact/normalized prompts, normalized complete references,
complete expected-output vectors, family IDs, declared function names, file
identifiers, same-category lexical similarity, and large ASTs after identifier and
constant normalization. AST screening omits short programs and does not prove
algorithmic distinction. Semantic equivalents with different implementation
structure may evade every lexical check. Conversely, ordinary shared concepts
listed above are intentional transfer targets, not evidence of memorized answers.
