-- -*- mode: sql -*-
--
-- Copyright 2014 the Critic contributors, Opera Software ASA
--
-- Licensed under the Apache License, Version 2.0 (the "License"); you may not
-- use this file except in compliance with the License.  You may obtain a copy of
-- the License at
--
--   http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing, software
-- distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
-- WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
-- License for the specific language governing permissions and limitations under
-- the License.

-- Changesets (i.e. differences) are represented in three levels:
--
--  * Structure / meta-data difference
--  * Content difference
--  * Content difference analysis
--
-- The structure difference consists of rows in the tables
--   changesets (1 row)
--   changesetfiles (1 row per added/removed/modified file)
-- and is fairly light-weight.  It can be calculated cheaply even for large
-- differences in big repositories.  The recorded information is sufficient to
-- maintain all necessary reviewing meta-data and state (but not to initially
-- create it.)
--
-- The content difference, which depends on the structure difference, consists
-- of rows in the tables
--   changesetfiledifferences (1 row per modified file)
--   changesetchangedlines (1+ rows per modified non-binary file)
-- and is more heavy-weight in nature.  It can be costly to calculate, in
-- particular for large differences in big repositories.  This level of
-- information is only required to display differences.
--
-- The content difference analysis, which depends on the content difference,
-- consists of the column
--   changesetchangedlines.analysis
-- and is also heavy-weight in nature.  It can be significantly expensive to
-- calculate in some cases.  This level of information is only required to
-- display side-by-side differences with inter-line difference highlighting.

-- Structure difference:
--   One row per changeset
CREATE TABLE changesets (
  id SERIAL PRIMARY KEY,

  -- Repository in which the difference is calculated.
  --
  -- The same pair of commits could be compared in multiple repositories (with
  -- necessarily identical results) but a reference is required to actually
  -- process the difference.  Optimizing for this seems unnecessary.
  repository INTEGER NOT NULL REFERENCES repositories ON DELETE CASCADE,
  -- "New"/"right-hand side" commit.
  to_commit INTEGER NOT NULL REFERENCES commits ON DELETE CASCADE,
  -- "Old"/"left-hand side" commit.  NULL means difference against the empty
  -- tree, e.g. because |to_commit| is a root commit.
  from_commit INTEGER REFERENCES commits ON DELETE CASCADE,
  -- If non-NULL, this is a "merge filtered" changeset, meaning the set of
  -- changed files recorded in changesetfiles is filtered to only include files
  -- changed on two or more sides of the merge.
  --
  -- This will only be set on changesets where either |to_commit| is the merge
  -- (same as |for_merge|) and |from_commit| is one of the parents, or
  -- changesets where |to_commit| is one of the parents and |from_commit| is the
  -- merge base.
  for_merge INTEGER REFERENCES commits ON DELETE CASCADE,
  -- If true, the |from_commit| is the result of replaying a merge or rebase,
  -- and may have conflict markers generated by Git checked in, for reference.
  -- This may trigger different analysis choices, and enables special syntax
  -- highlighting of the conflict marker lines.
  is_replay BOOLEAN NOT NULL DEFAULT FALSE,

  -- Set to TRUE when the structure difference has been preliminarily
  -- calculated.
  processed BOOLEAN NOT NULL DEFAULT FALSE,
  -- Set to TRUE when the structure difference has been fully calculated.  At
  -- this time, all rows in changesetfiles make up the structure difference will
  -- have been inserted.  Even before that, some of those rows may have been
  -- insterted.
  complete BOOLEAN NOT NULL DEFAULT FALSE
);

-- Index for lookup speed and to ensure uniqueness of non-partial changesets.
CREATE UNIQUE INDEX changesets_regular
  ON changesets (repository, to_commit, from_commit)
  WHERE for_merge IS NULL;

-- Index for lookup speed of partial changesets.
CREATE UNIQUE INDEX changesets_for_merge
  ON changesets (repository, to_commit, from_commit, for_merge)
  WHERE for_merge IS NOT NULL;

-- General:
--   One row per error during changeset processing
--
-- Rows in this table disable further attempts to perform the failed job until
-- cleared, to avoid endless spamming.  They also serve to indicate to clients
-- that there's a problem and that they should not expect a finished result any
-- time soon.
CREATE TABLE changeseterrors (
  changeset INTEGER REFERENCES changesets ON DELETE CASCADE,

  -- A job key is a Python tuple containing the class name of the job and a
  -- small number of integers and in some cases a SHA-1 sum.  This column
  -- contains a string produced converting this tuple to JSON.
  job_key VARCHAR(256),

  -- Fatality.  A fatal error means the content difference is not usable.  A
  -- non-fatal error will simply lead to reduced functionality.
  fatal BOOLEAN NOT NULL,

  -- A Python traceback.
  traceback TEXT NOT NULL,

  PRIMARY KEY (changeset, job_key)
);

-- Structure difference:
--   One row per added/removed/modified file.
--
-- Matched by one row in changesetfiledifferences iff content difference has
-- been calculated.
--
-- Note that added/removed/modified sub-module entries are represented as files
-- in this context, but the SHA-1 is of a commit in the sub-module repository
-- rather than a blob in "this" repository.
CREATE TABLE changesetfiles (
  changeset INTEGER REFERENCES changesets ON DELETE CASCADE,
  file INTEGER REFERENCES files,

  -- Old SHA-1.  NULL means "non-existing", i.e. file was added.
  old_sha1 CHAR(40),
  -- Old file mode.  NULL means "non-existing", i.e. file was added.
  old_mode INTEGER,
  -- New SHA-1.  NULL means "non-existing", i.e. file was removed.
  new_sha1 CHAR(40),
  -- Old file mode.  NULL means "non-existing", i.e. file was removed.
  new_mode INTEGER,

  PRIMARY KEY (changeset, file)
);

CREATE TABLE highlightlanguages (
  id SERIAL PRIMARY KEY,
  label VARCHAR(64) NOT NULL UNIQUE
);

-- Syntax highlighting request:
--   One row per file version that needs to be highlighted in a changeset.
CREATE TABLE highlightfiles (
  id SERIAL PRIMARY KEY,

  repository INTEGER NOT NULL,
  sha1 CHAR(40) NOT NULL,
  -- Language the file is or should be highlighted as. NULL means no language
  -- could be detected, and that the file should not be highlighted.
  language INTEGER,
  conflicts BOOLEAN NOT NULL,

  -- Whether this file is currently highlighted; IOW, whether lines exists in
  -- the |highlightlines| table.
  highlighted BOOLEAN DEFAULT FALSE,
  -- Whether this file should be highlighted, when it isn't.
  requested BOOLEAN DEFAULT TRUE,

  FOREIGN KEY (repository)
    REFERENCES repositories ON DELETE CASCADE,
  FOREIGN KEY (language)
    REFERENCES highlightlanguages ON DELETE SET NULL,

  -- It is not valid for |requested| to be TRUE if |highlighted| is also TRUE.
  -- Both can be FALSE, or one of them TRUE, but never both.
  CHECK (NOT requested OR NOT highlighted)
);
CREATE UNIQUE INDEX highlightfiles_repository_sha1
                 ON highlightfiles (
                      repository, sha1, COALESCE(language, -1), conflicts
                    );

CREATE TABLE highlightlines (
  file INTEGER NOT NULL,
  line INTEGER NOT NULL,
  data BYTEA NOT NULL,

  PRIMARY KEY (file, line),
  FOREIGN KEY (file)
    REFERENCES highlightfiles ON DELETE CASCADE
);

-- Content difference:
--   One row per changeset
--
-- Matches one row in changesets (the structure difference).
--
-- Inserting a row into this table represents a request for the content
-- difference to be calculated.  Once calculated, the |complete| column is set
-- to TRUE.
--
-- The |requested| column contains a timestamp that is used to determine when
-- the content difference should be garbage collected.
CREATE TABLE changesetcontentdifferences (
  changeset INTEGER PRIMARY KEY REFERENCES changesets ON DELETE CASCADE,

  -- Timestamp of request or last use.  Used to determine when it makes sense to
  -- garbage collect (i.e. delete) the content difference to save space.
  requested TIMESTAMP NOT NULL DEFAULT NOW(),
  -- Set to TRUE when the content difference has been fully calculated.  At this
  -- time, all rows in changesetfiledifferences and changesetchangedlines that
  -- make up the content difference will have been inserted.  Even before that,
  -- some of those rows may have been insterted.
  complete BOOLEAN NOT NULL DEFAULT FALSE
);

-- Content difference:
--   One row per added/removed/modified regular file or symbolic link.
--
-- Matches one row in changesetfiles (the structure difference).
--
-- Iff either old_is_binary or new_is_binary is FALSE (i.e. neither NULL nor
-- TRUE) then a row will be matched by at least one row in
-- changesetchangedlines, once the content difference has been fully processed.
CREATE TABLE changesetfiledifferences (
  changeset INTEGER,
  file INTEGER,

  -- TRUE if the file versions will be compared but has not been compared yet.
  -- If the file was either added or removed, or modified but at least one of
  -- the versions is binary, this value is set to FALSE initially, otherwise it
  -- is set to FALSE when corresponding rows have been inserted into the
  -- |changesetchangedlines| table.
  comparison_pending BOOLEAN,

  -- TRUE if old version is binary. NULL means "non-existing", i.e. file was
  -- added.
  old_is_binary BOOLEAN,
  -- Number of lines in the old version. NULL means "non-existing" or that the
  -- file is binary (use `old_is_binary` to differentiate.)
  old_length INTEGER,
  -- TRUE if the old version has a trailing line-break. NULL means
  -- "non-existing", i.e. file was added.
  old_linebreak BOOLEAN,
  -- The syntax highlighting record for the old version of the file. NULL if the
  -- file was added.
  old_highlightfile INTEGER,
  -- TRUE if new version is binary. NULL means "non-existing", i.e. file was
  -- removed.
  new_is_binary BOOLEAN,
  -- Number of lines in the new version. NULL means "non-existing" or that the
  -- file is binary (use `new_is_binary` to differentiate.)
  new_length INTEGER,
  -- TRUE if the new version has a trailing line-break. NULL means
  -- "non-existing", i.e. file was added.
  new_linebreak BOOLEAN,
  -- The syntax highlighting record for the new version of the file. NULL if the
  -- file was removed.
  new_highlightfile INTEGER,

  PRIMARY KEY (changeset, file),
  FOREIGN KEY (changeset)
    REFERENCES changesetcontentdifferences ON DELETE CASCADE,
  FOREIGN KEY (changeset, file)
    REFERENCES changesetfiles ON DELETE CASCADE,
  FOREIGN KEY (old_highlightfile)
    REFERENCES highlightfiles ON DELETE CASCADE,
  FOREIGN KEY (new_highlightfile)
    REFERENCES highlightfiles ON DELETE CASCADE
);
CREATE INDEX changesetfiledifferences_old_highlightfile
          ON changesetfiledifferences (old_highlightfile);
CREATE INDEX changesetfiledifferences_new_highlightfile
          ON changesetfiledifferences (new_highlightfile);

CREATE VIEW changesetmodifiedregularfiles
  AS SELECT changeset, file, old_sha1, old_mode, new_sha1, new_mode
       FROM changesetfiles
       JOIN changesetfiledifferences USING (changeset, file)
      WHERE old_sha1 IS NOT NULL
        AND new_sha1 IS NOT NULL
        AND old_sha1 != new_sha1
        AND ((old_mode | new_mode) & 261632) = 32768
        AND NOT old_is_binary
        AND NOT new_is_binary;

-- Content difference:
--   Zero or more rows per added/removed/modified regular file.
--
-- Each row represents one block of lines in the old version being replaced by
-- one block of lines in the new version.  Either of these blocks can be empty,
-- meaning lines were only added (delete_count=0) or removed (insert_count=0).
--
-- Added or removed files are represented as a single block of changed lines
-- that adds or removes all lines at offset zero.  This simply serves to record
-- the number of lines in the added or removed file.
--
-- Binary files being added, removed or modified is represented by no rows.  A
-- file being modified so that it becomes or stops being binary is represented
-- by a single row, as if the non-binary version had been removed or added.
--
-- A zero-length file is represented as a non-binary file that has zero lines.
--
-- A symbolic link is represented as a text file containing a single line.
--
-- A sub-module file ("git link") is represented as a binary file.
CREATE TABLE changesetchangedlines (
  changeset INTEGER,
  file INTEGER,

  -- Zero-based block index.
  "index" INTEGER NOT NULL,

  -- Offset (number of lines) from preceding block of changed lines, or from the
  -- beginning of the file if |index=0|. Can only be zero if |index=0|.
  "offset" INTEGER NOT NULL,

  -- Number of deleted lines, i.e. lines that existed in the old version but
  -- don't exist in the new version.
  delete_count INTEGER NOT NULL,
  -- Length of the block in the old version.  This is |delete_count| plus any
  -- lines that were included despite being identical.
  delete_length INTEGER NOT NULL,

  -- Number of inserted lines, i.e. lines that exist in the new version but
  -- didn't exist in the old version.
  insert_count INTEGER NOT NULL,
  -- Length of the block in the new version.  This is |insert_count| plus any
  -- lines that were included despite being identical.
  insert_length INTEGER NOT NULL,

  -- Content difference analysis.  NULL if not processed yet.  Always set to
  -- non-NULL by processing; set to empty string if there's no relevant result
  -- (e.g. because lines were only added or removed.)
  analysis TEXT,

  PRIMARY KEY (changeset, file, "index"),

  FOREIGN KEY (changeset, file)
    REFERENCES changesetfiledifferences ON DELETE CASCADE,

  -- Implementation detail: blocks of changed lines that represent a pure
  -- removal of lines or insertion of lines, i.e. where either |delete_count| or
  -- |insert_count| is zero, has no relevant analysis.  Make sure we always set
  -- the analysis to the empty string on insertion, rather than inserting NULL,
  -- thus "scheduling" a pointless analysis of the block.
  CHECK (analysis IS NOT NULL OR (delete_count!=0 AND insert_count!=0))
);

-- Syntax highlighting request:
--   One row per changeset with files that need to be highlighted.
CREATE TABLE changesethighlightrequests (
  -- Reference the content difference.  When the content difference is garbage
  -- collected, so will the syntax highlighted copies of the files be, unless
  -- they are referenced via other changesets as well.
  changeset INTEGER,

  -- Set to TRUE when all changed files in the changeset have been evaluated
  -- (the appropriate language to syntax highlight as has been calculated,)
  -- individual syntax highlight requests for each file that should be syntax
  -- highlighted have been inserted into |highlightfiles|.
  evaluated BOOLEAN NOT NULL DEFAULT FALSE,

  -- If TRUE, rows inserted into |highlightfiles| will have their |requested|
  -- column set to TRUE as well. Updating this column later has no effect; to
  -- re-request deleted syntax highlighting, the |highlightfiles.requested|
  -- column should be updated instead.
  requested BOOLEAN NOT NULL DEFAULT TRUE,

  PRIMARY KEY (changeset),
  FOREIGN KEY (changeset)
    REFERENCES changesetcontentdifferences ON DELETE CASCADE
);

-- Custom syntax highlighting request:
--   One row per file version that needs to be highlighted.
--
-- The actual files to highlight are stored in |highlightfiles|.
CREATE TABLE customhighlightrequests (
  id SERIAL PRIMARY KEY,

  file INTEGER NOT NULL,

  -- Time of last access of the highlighted file. This is used to determine when
  -- to drop the highlight data to save space.
  last_access TIMESTAMP NOT NULL DEFAULT NOW(),

  FOREIGN KEY (file)
    REFERENCES highlightfiles ON DELETE CASCADE
);

CREATE INDEX customhighlightrequests_file
          ON customhighlightrequests (file);

-- Merge replay request:
--   One row per merge commit to replay.
CREATE TABLE mergereplayrequests (
  repository INTEGER REFERENCES repositories ON DELETE CASCADE,
  -- Original merge commit to replay.
  merge INTEGER REFERENCES commits ON DELETE CASCADE,

  -- The merge commit produced by replaying or NULL if not replayed yet.
  replay INTEGER REFERENCES commits,
  -- A Python traceback, if replaying failed.  NULL otherwise.
  traceback TEXT,

  PRIMARY KEY (repository, merge),
  CHECK (replay IS NULL OR traceback IS NULL)
);

-- Code contexts:
--   One row per range of lines with a label.
--
-- Calculated as a side-effect of syntax highlighting in a language dependent
-- way.  Not all languages support this.
CREATE TABLE codecontexts (
  -- The syntax highlighted blob's SHA-1 sum.
  sha1 CHAR(40),
  -- Language used to syntax highlight.
  language INTEGER NOT NULL REFERENCES highlightlanguages,
  -- Zero-based offset of first line covered by context.
  first_line INTEGER NOT NULL,
  -- Zero-based offset of last line covered by context.
  last_line INTEGER NOT NULL,

  context TEXT NOT NULL,

  PRIMARY KEY (sha1, language, first_line, last_line)
);