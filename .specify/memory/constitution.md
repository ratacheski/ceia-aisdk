<!--
Sync Impact Report
- Version change: unratified template -> 1.0.0
- Modified principles:
  - Template Principle 1 -> I. PyPI-Ready Library
  - Template Principle 2 -> II. SpecKit-First Development
  - Template Principle 3 -> III. Test-First Development (NON-NEGOTIABLE)
  - Template Principle 4 -> IV. English-Only Repository
  - Template Principle 5 -> V. Complete Public Interface Documentation
- Added sections:
  - Packaging and Tooling Constraints
  - Development Workflow and Quality Gates
- Removed sections: None
- Follow-up TODOs: None
-->
# CEIA AI SDK Constitution

## Core Principles

### I. PyPI-Ready Library

The repository MUST remain a coherent Python package that can be built as both a wheel and a
source distribution. Every merged change MUST preserve package installation, importability,
version metadata, and the documented public interfaces. PyPI is the only public distribution
channel for the SDK; models, generated caches, and other runtime assets MUST NOT be embedded in
package artifacts. Publication timing and versioning MUST follow the approved SpecKit artifacts
and release plan.

Rationale: package readiness at every increment prevents late release failures and keeps the
repository aligned with its intended product form.

### II. SpecKit-First Development

Every user-visible feature, bug fix, behavior change, and breaking change MUST be represented by
current SpecKit artifacts before production code is changed. Work MUST proceed in this order:
specification, clarification when required, plan, dependency-ordered tasks, and implementation.
Requirements, acceptance scenarios, plans, and tasks MUST remain traceable to one another and to
the resulting tests and code. Implementations MUST NOT introduce behavior that is absent from the
approved specification.

Rationale: SpecKit is the repository's system of record for scope, decisions, acceptance, and
delivery status.

### III. Test-First Development (NON-NEGOTIABLE)

All behavior changes MUST follow the red-green-refactor cycle. An automated test MUST be written
first and observed failing for the expected reason before production code is added or changed.
The smallest implementation that makes the test pass MUST follow, after which refactoring may
occur while the suite remains green. Public interfaces MUST have contract or integration coverage
in addition to focused unit coverage where applicable. Documentation-only changes MUST pass their
applicable validation checks but do not require an artificial executable test.

Rationale: observable failing tests prove that changes are required, protect public contracts,
and prevent regressions while the SDK evolves.

### IV. English-Only Repository

Source code, identifiers maintained by the project, comments, docstrings, CLI help, error
messages, examples, user documentation, and all SpecKit artifacts MUST be written in English.
Non-English text is permitted only in fixtures that explicitly test multilingual input or output,
and the fixture purpose MUST be documented in English. Existing non-English artifacts are
migration debt and MUST be translated before they are used to authorize implementation or are
included in a public release.

Rationale: one repository language keeps review, maintenance, generated documentation, and public
support consistent for an international package.

### V. Complete Public Interface Documentation

Every method, including non-public methods maintained by the project, MUST have an English
docstring that states its purpose and documents parameters, return values, raised exceptions, and
relevant side effects. Public modules, classes, and functions MUST also have English docstrings.
Every SDK command and subcommand MUST expose help text describing its purpose, every argument and
option, required status, defaults, constraints, and at least one executable usage example. Root
help MUST make all available commands discoverable. No undocumented interface may be merged.

Rationale: the package and CLI must be usable without reading implementation details or searching
for undocumented behavior.

## Packaging and Tooling Constraints

- `uv` MUST be used for dependency declaration, resolution, locking, environment synchronization,
  command execution in project environments, package builds, and publication.
- Dependency changes MUST update both `pyproject.toml` and `uv.lock` through `uv`; lockfiles MUST
  NOT be edited manually.
- The committed lockfile MUST be synchronized with project metadata and reproducible in continuous
  integration.
- A clean checkout MUST build valid wheel and source distribution artifacts with `uv build`.
- Package metadata MUST use the approved `ceia-aisdk` distribution name, accurately declare the
  supported Python and operating-system scope, and contain no unsupported compatibility claims.
- Public releases MUST be uploaded only to PyPI using the approved release process. Test indexes
  may be used for validation but do not constitute a public release.
- Documentation examples MUST use `uv` commands for contributor workflows. End-user installation
  examples may use standard PyPI installation commands when that is the supported user contract.

## Development Workflow and Quality Gates

1. **Specify**: Create or update the relevant SpecKit specification and resolve material
   clarifications before planning.
2. **Plan**: Record architecture, dependencies, constitution compliance, and validation strategy
   in the feature plan.
3. **Task**: Generate dependency-ordered tasks that explicitly include tests, English
   documentation, docstrings, CLI help, and package validation where applicable.
4. **Red**: Add the smallest test that demonstrates the required behavior and verify that it fails
   for the expected reason.
5. **Green and refactor**: Implement only the specified behavior, make the test pass, and improve
   structure without breaking the suite.
6. **Validate**: Before merge, all applicable checks MUST pass through the `uv`-managed
   environment:
   - the complete automated test suite;
   - dependency lock and environment synchronization checks;
   - wheel and source distribution builds;
   - docstring and documentation validation;
   - English-language review of source, documentation, and SpecKit artifacts;
   - runtime checks that every command's help is complete and every example is valid.
7. **Review**: Reviewers MUST verify traceability from specification to tests and implementation,
   and MUST reject changes that bypass any applicable gate.

Continuous integration MUST enforce the automatable gates. Any temporary exception MUST be
explicitly approved, documented in the feature plan with an owner and expiry condition, and MUST
NOT weaken the test-first rule or permit an undocumented public interface.

## Governance

This constitution supersedes conflicting repository practices, plans, and conventions. Every
SpecKit plan and every code review MUST include a constitution compliance check. A change that is
not compliant MUST NOT merge or be published.

Amendments MUST be proposed as a dedicated documentation change that states the rationale,
migration impact, and affected principles. Approval requires explicit maintainer acceptance and an
updated Sync Impact Report. Constitution versions follow semantic versioning:

- MAJOR for removal or backward-incompatible redefinition of a principle or governance rule;
- MINOR for a new principle, section, or materially expanded obligation;
- PATCH for wording improvements and non-semantic clarification.

The ratification date records initial adoption and does not change. The last-amended date MUST
change whenever normative content changes. When an amendment creates migration work, the
amendment MUST identify the non-compliant artifacts and define when they block planning, merge, or
release.

**Version**: 1.0.0 | **Ratified**: 2026-09-01 | **Last Amended**: 2026-09-01
