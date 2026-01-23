# SecondaBrain - Development Ticket Stream

> **Project**: SecondaBrain - Personal Knowledge Management System
> **Generated**: 2026-01-23
> **Status**: Backlog Ready for Implementation

## Project Assumptions

Based on the project name "secondabrain", this backlog assumes:
- A personal knowledge management system (PKM) similar to Obsidian/Notion
- Web-based application with modern stack
- Single-user local-first architecture (extensible to multi-user later)
- Markdown-based note storage
- Tag and folder organization
- Bidirectional linking between notes
- Full-text search capabilities

**Recommended Tech Stack**:
- **Frontend**: React + TypeScript + Vite
- **Backend**: Node.js + Express (or serverless functions)
- **Storage**: SQLite (local) / PostgreSQL (cloud)
- **Search**: Lunr.js (client-side) or MeiliSearch
- **Styling**: Tailwind CSS

---

# EPIC 1: Project Foundation & Setup

> Establish the project structure, tooling, and development environment.

## Story 1.1: Initialize Project Structure

### Ticket 1.1.1: Create package.json with project metadata
- **Description**: Initialize npm project with name, version, description, and scripts
- **Files to Create**: `package.json`
- **Acceptance Criteria**:
  - package.json exists with name "secondabrain"
  - Contains scripts for dev, build, test, lint
  - Specifies Node.js engine requirements (>=18)
- **Test Expectations**: `npm run` lists available scripts without error

### Ticket 1.1.2: Configure TypeScript
- **Description**: Set up TypeScript configuration for strict type checking
- **Files to Create**: `tsconfig.json`
- **Acceptance Criteria**:
  - Strict mode enabled
  - ES2022 target with ESM modules
  - Path aliases configured (@/ for src)
  - Include/exclude patterns properly set
- **Test Expectations**: `npx tsc --noEmit` runs without errors

### Ticket 1.1.3: Configure ESLint and Prettier
- **Description**: Set up code quality and formatting tools
- **Files to Create**: `.eslintrc.cjs`, `.prettierrc`, `.prettierignore`
- **Acceptance Criteria**:
  - ESLint configured for TypeScript
  - Prettier integrated with ESLint
  - Consistent code style rules defined
- **Test Expectations**: `npm run lint` executes without configuration errors

### Ticket 1.1.4: Create .gitignore file
- **Description**: Configure git to ignore build artifacts, dependencies, and secrets
- **Files to Create**: `.gitignore`
- **Acceptance Criteria**:
  - node_modules ignored
  - dist/build folders ignored
  - .env files ignored
  - IDE-specific files ignored
- **Test Expectations**: `git status` doesn't show ignored files

### Ticket 1.1.5: Set up directory structure
- **Description**: Create the base folder structure for the application
- **Files to Create**:
  - `src/index.ts` (entry point placeholder)
  - `src/types/index.ts` (type exports placeholder)
  - `src/utils/index.ts` (utility exports placeholder)
  - `src/components/.gitkeep`
  - `src/services/.gitkeep`
  - `tests/.gitkeep`
- **Acceptance Criteria**:
  - All directories exist
  - Placeholder files are valid TypeScript
- **Test Expectations**: Project structure matches specification

---

## Story 1.2: Configure Build & Dev Environment

### Ticket 1.2.1: Install and configure Vite
- **Description**: Set up Vite as the build tool and dev server
- **Files to Create**: `vite.config.ts`
- **Files to Modify**: `package.json` (add dependencies)
- **Acceptance Criteria**:
  - Vite configured for React + TypeScript
  - Dev server runs on port 5173
  - Build outputs to dist/
  - Path aliases work correctly
- **Test Expectations**: `npm run dev` starts dev server; `npm run build` creates dist/

### Ticket 1.2.2: Configure Vitest for testing
- **Description**: Set up Vitest as the test runner
- **Files to Create**: `vitest.config.ts`
- **Files to Modify**: `package.json` (add test scripts and dependencies)
- **Acceptance Criteria**:
  - Vitest configured with TypeScript support
  - Coverage reporting enabled
  - Watch mode available
- **Test Expectations**: `npm test` runs without errors (even with no tests)

### Ticket 1.2.3: Create environment configuration
- **Description**: Set up environment variable handling
- **Files to Create**: `.env.example`, `src/config/env.ts`
- **Acceptance Criteria**:
  - Example env file documents required variables
  - Type-safe environment variable access
  - Validation for required variables
- **Test Expectations**: App throws clear error if required env vars missing

---

# EPIC 2: Data Models & Storage Layer

> Define the core data structures and persistence mechanisms.

## Story 2.1: Define Core Data Types

### Ticket 2.1.1: Create Note type definition
- **Description**: Define the TypeScript interface for a Note entity
- **Files to Create**: `src/types/note.ts`
- **Acceptance Criteria**:
  - Note has: id (string/uuid), title, content, createdAt, updatedAt
  - Note has: tags (string[]), folderId (optional)
  - All fields properly typed
  - Export interface and any utility types
- **Test Expectations**: Type compiles; can create valid Note objects

### Ticket 2.1.2: Create Folder type definition
- **Description**: Define the TypeScript interface for a Folder entity
- **Files to Create**: `src/types/folder.ts`
- **Acceptance Criteria**:
  - Folder has: id, name, parentId (optional for nesting), createdAt
  - Supports hierarchical structure
- **Test Expectations**: Type compiles; can represent nested folder structure

### Ticket 2.1.3: Create Tag type definition
- **Description**: Define the TypeScript interface for a Tag entity
- **Files to Create**: `src/types/tag.ts`
- **Acceptance Criteria**:
  - Tag has: id, name, color (optional)
  - Name is unique identifier
- **Test Expectations**: Type compiles

### Ticket 2.1.4: Create Link type definition
- **Description**: Define the TypeScript interface for bidirectional links
- **Files to Create**: `src/types/link.ts`
- **Acceptance Criteria**:
  - Link has: sourceNoteId, targetNoteId, context (optional snippet)
  - Represents [[wiki-style]] links between notes
- **Test Expectations**: Type compiles; can represent note connections

### Ticket 2.1.5: Create index barrel file for types
- **Description**: Export all types from a single entry point
- **Files to Modify**: `src/types/index.ts`
- **Acceptance Criteria**:
  - All types exported from index
  - Clean import syntax: `import { Note, Folder } from '@/types'`
- **Test Expectations**: All types importable from single path

---

## Story 2.2: Implement Storage Service

### Ticket 2.2.1: Create storage interface
- **Description**: Define abstract storage interface for persistence operations
- **Files to Create**: `src/services/storage/types.ts`
- **Acceptance Criteria**:
  - IStorageService interface with CRUD operations
  - Generic methods: get, set, delete, list, query
  - Async/Promise-based API
- **Test Expectations**: Interface compiles; documents expected behavior

### Ticket 2.2.2: Implement LocalStorage adapter
- **Description**: Create browser LocalStorage implementation of storage interface
- **Files to Create**: `src/services/storage/localStorage.ts`
- **Acceptance Criteria**:
  - Implements IStorageService
  - JSON serialization for complex objects
  - Handles storage quota errors gracefully
  - Namespaced keys to avoid conflicts
- **Test Expectations**: Can store and retrieve Note objects

### Ticket 2.2.3: Implement IndexedDB adapter
- **Description**: Create IndexedDB implementation for larger storage needs
- **Files to Create**: `src/services/storage/indexedDB.ts`
- **Acceptance Criteria**:
  - Implements IStorageService
  - Database versioning and migrations
  - Object stores for notes, folders, tags
  - Index on common query fields
- **Test Expectations**: Can store 1000+ notes without performance issues

### Ticket 2.2.4: Create storage factory
- **Description**: Factory function to select appropriate storage backend
- **Files to Create**: `src/services/storage/index.ts`
- **Acceptance Criteria**:
  - Auto-detects best available storage
  - Falls back gracefully (IndexedDB → LocalStorage)
  - Exports unified storage instance
- **Test Expectations**: Factory returns working storage instance

---

## Story 2.3: Implement Note Repository

### Ticket 2.3.1: Create NoteRepository class
- **Description**: Repository pattern wrapper for note CRUD operations
- **Files to Create**: `src/repositories/noteRepository.ts`
- **Acceptance Criteria**:
  - Methods: create, getById, update, delete, listAll
  - Generates UUIDs for new notes
  - Auto-sets createdAt/updatedAt timestamps
- **Test Expectations**: All CRUD operations work correctly

### Ticket 2.3.2: Add note search method to repository
- **Description**: Add full-text search capability to note repository
- **Files to Modify**: `src/repositories/noteRepository.ts`
- **Acceptance Criteria**:
  - search(query: string) method
  - Searches title and content
  - Returns matching notes sorted by relevance
- **Test Expectations**: Search finds notes containing query terms

### Ticket 2.3.3: Add note filtering methods
- **Description**: Add methods to filter notes by folder and tags
- **Files to Modify**: `src/repositories/noteRepository.ts`
- **Acceptance Criteria**:
  - getByFolder(folderId) method
  - getByTag(tagName) method
  - getByTags(tagNames, mode: 'AND' | 'OR') method
- **Test Expectations**: Filters return correct subsets

---

# EPIC 3: Core Note Operations

> Implement the fundamental note creation, editing, and management features.

## Story 3.1: Note CRUD Service

### Ticket 3.1.1: Create NoteService class
- **Description**: Service layer for note business logic
- **Files to Create**: `src/services/noteService.ts`
- **Acceptance Criteria**:
  - Wraps NoteRepository
  - Validates note data before persistence
  - Emits events on note changes (for UI updates)
- **Test Expectations**: Service methods call repository correctly

### Ticket 3.1.2: Implement note validation
- **Description**: Add validation rules for note creation/updates
- **Files to Create**: `src/utils/validation/noteValidation.ts`
- **Acceptance Criteria**:
  - Title required, max 200 characters
  - Content max 100,000 characters
  - Tags array validated (no duplicates, valid format)
  - Returns structured validation errors
- **Test Expectations**: Invalid notes rejected with clear errors

### Ticket 3.1.3: Implement note sanitization
- **Description**: Sanitize note content to prevent XSS
- **Files to Create**: `src/utils/sanitize.ts`
- **Acceptance Criteria**:
  - HTML entities escaped in user content
  - Markdown preserved
  - Links validated
- **Test Expectations**: Script tags and event handlers neutralized

---

## Story 3.2: Markdown Processing

### Ticket 3.2.1: Set up markdown parser
- **Description**: Configure markdown-it or similar for parsing
- **Files to Create**: `src/services/markdown/parser.ts`
- **Files to Modify**: `package.json` (add dependency)
- **Acceptance Criteria**:
  - Parses standard markdown syntax
  - Generates safe HTML output
  - Supports code highlighting
- **Test Expectations**: Markdown renders to expected HTML

### Ticket 3.2.2: Implement wiki-link syntax extension
- **Description**: Add [[wiki-link]] parsing support
- **Files to Create**: `src/services/markdown/wikiLinks.ts`
- **Acceptance Criteria**:
  - Recognizes [[Note Title]] syntax
  - Extracts link targets from content
  - Renders as clickable internal links
- **Test Expectations**: [[Test Note]] becomes link to "Test Note"

### Ticket 3.2.3: Implement tag extraction
- **Description**: Extract #tags from note content
- **Files to Create**: `src/services/markdown/tagExtractor.ts`
- **Acceptance Criteria**:
  - Recognizes #tag and #multi-word-tag syntax
  - Returns array of unique tags
  - Handles edge cases (code blocks, URLs)
- **Test Expectations**: "Hello #world #test" extracts ["world", "test"]

### Ticket 3.2.4: Create markdown preview renderer
- **Description**: Component to render markdown as HTML preview
- **Files to Create**: `src/components/MarkdownPreview.tsx`
- **Acceptance Criteria**:
  - Accepts markdown string prop
  - Renders sanitized HTML
  - Applies consistent styling
- **Test Expectations**: Component renders without errors

---

## Story 3.3: Link Management

### Ticket 3.3.1: Create LinkService class
- **Description**: Service to manage bidirectional links between notes
- **Files to Create**: `src/services/linkService.ts`
- **Acceptance Criteria**:
  - extractLinks(noteContent) - finds all [[links]]
  - updateLinks(noteId, content) - syncs link records
  - getBacklinks(noteId) - finds notes linking to this one
- **Test Expectations**: Backlinks accurately reflect forward links

### Ticket 3.3.2: Implement link resolution
- **Description**: Resolve [[Note Title]] to actual note IDs
- **Files to Modify**: `src/services/linkService.ts`
- **Acceptance Criteria**:
  - Matches by exact title
  - Handles case variations
  - Returns null for broken links
- **Test Expectations**: Valid links resolve; invalid return null

### Ticket 3.3.3: Create broken link detector
- **Description**: Identify and report broken internal links
- **Files to Create**: `src/services/linkService.ts` (add method)
- **Acceptance Criteria**:
  - getBrokenLinks() returns all unresolved links
  - Includes source note and link text
- **Test Expectations**: Broken links correctly identified

---

# EPIC 4: User Interface Components

> Build the React component library for the application.

## Story 4.1: Layout Components

### Ticket 4.1.1: Create App shell layout
- **Description**: Main application layout with sidebar and content area
- **Files to Create**: `src/components/layout/AppShell.tsx`
- **Acceptance Criteria**:
  - Responsive layout (mobile-friendly)
  - Collapsible sidebar
  - Main content area fills remaining space
- **Test Expectations**: Layout renders at various viewport sizes

### Ticket 4.1.2: Create Sidebar component
- **Description**: Navigation sidebar with folder tree and actions
- **Files to Create**: `src/components/layout/Sidebar.tsx`
- **Acceptance Criteria**:
  - Displays folder hierarchy
  - Shows recent notes
  - Quick action buttons (new note, search)
- **Test Expectations**: Sidebar renders with mock folder data

### Ticket 4.1.3: Create Header component
- **Description**: Top header bar with search and settings
- **Files to Create**: `src/components/layout/Header.tsx`
- **Acceptance Criteria**:
  - Search input field
  - Settings/menu button
  - App title/logo area
- **Test Expectations**: Header renders with functional search input

---

## Story 4.2: Note Components

### Ticket 4.2.1: Create NoteList component
- **Description**: List view of notes with title and preview
- **Files to Create**: `src/components/notes/NoteList.tsx`
- **Acceptance Criteria**:
  - Displays note title and content preview
  - Shows last modified date
  - Click selects note
  - Empty state when no notes
- **Test Expectations**: Renders list of notes; handles empty array

### Ticket 4.2.2: Create NoteListItem component
- **Description**: Individual note item in list view
- **Files to Create**: `src/components/notes/NoteListItem.tsx`
- **Acceptance Criteria**:
  - Shows title, preview (first 100 chars), date
  - Visual selected state
  - Hover state
- **Test Expectations**: Item renders note data correctly

### Ticket 4.2.3: Create NoteEditor component
- **Description**: Main note editing interface
- **Files to Create**: `src/components/notes/NoteEditor.tsx`
- **Acceptance Criteria**:
  - Title input field
  - Content textarea/editor
  - Auto-save on change (debounced)
  - Markdown syntax support
- **Test Expectations**: Editor loads note and saves changes

### Ticket 4.2.4: Create NoteToolbar component
- **Description**: Toolbar with formatting and action buttons
- **Files to Create**: `src/components/notes/NoteToolbar.tsx`
- **Acceptance Criteria**:
  - Bold, italic, heading buttons
  - Link insertion
  - Delete note button
- **Test Expectations**: Toolbar buttons trigger expected callbacks

### Ticket 4.2.5: Create TagInput component
- **Description**: Input for adding/removing tags on notes
- **Files to Create**: `src/components/notes/TagInput.tsx`
- **Acceptance Criteria**:
  - Displays current tags as chips
  - Autocomplete from existing tags
  - Add new tags by typing
  - Remove tags by clicking X
- **Test Expectations**: Tags can be added and removed

---

## Story 4.3: Navigation Components

### Ticket 4.3.1: Create FolderTree component
- **Description**: Hierarchical folder navigation tree
- **Files to Create**: `src/components/navigation/FolderTree.tsx`
- **Acceptance Criteria**:
  - Expandable/collapsible folders
  - Click selects folder
  - Shows note count per folder
- **Test Expectations**: Tree renders nested folder structure

### Ticket 4.3.2: Create SearchResults component
- **Description**: Display search results with highlighting
- **Files to Create**: `src/components/navigation/SearchResults.tsx`
- **Acceptance Criteria**:
  - Shows matching notes
  - Highlights search term in results
  - Click navigates to note
- **Test Expectations**: Results display with query highlighting

### Ticket 4.3.3: Create Breadcrumb component
- **Description**: Show current location in folder hierarchy
- **Files to Create**: `src/components/navigation/Breadcrumb.tsx`
- **Acceptance Criteria**:
  - Shows path: Home > Folder > Subfolder
  - Each segment clickable
- **Test Expectations**: Breadcrumb renders path correctly

---

# EPIC 5: State Management

> Implement application state management and data flow.

## Story 5.1: Store Setup

### Ticket 5.1.1: Configure Zustand store
- **Description**: Set up Zustand for global state management
- **Files to Create**: `src/store/index.ts`
- **Files to Modify**: `package.json` (add zustand)
- **Acceptance Criteria**:
  - Store configured with TypeScript
  - Persist middleware for state persistence
  - DevTools integration
- **Test Expectations**: Store initializes without errors

### Ticket 5.1.2: Create notes slice
- **Description**: State slice for notes data
- **Files to Create**: `src/store/notesSlice.ts`
- **Acceptance Criteria**:
  - State: notes array, selectedNoteId, isLoading
  - Actions: setNotes, addNote, updateNote, deleteNote, selectNote
- **Test Expectations**: Actions modify state correctly

### Ticket 5.1.3: Create folders slice
- **Description**: State slice for folders data
- **Files to Create**: `src/store/foldersSlice.ts`
- **Acceptance Criteria**:
  - State: folders array, selectedFolderId, expandedFolderIds
  - Actions: setFolders, addFolder, deleteFolder, toggleExpand
- **Test Expectations**: Actions modify state correctly

### Ticket 5.1.4: Create search slice
- **Description**: State slice for search functionality
- **Files to Create**: `src/store/searchSlice.ts`
- **Acceptance Criteria**:
  - State: query, results, isSearching
  - Actions: setQuery, setResults, clearSearch
- **Test Expectations**: Search state updates correctly

### Ticket 5.1.5: Create UI slice
- **Description**: State slice for UI preferences
- **Files to Create**: `src/store/uiSlice.ts`
- **Acceptance Criteria**:
  - State: sidebarCollapsed, theme, viewMode
  - Actions: toggleSidebar, setTheme, setViewMode
- **Test Expectations**: UI state persists across sessions

---

## Story 5.2: Data Loading & Sync

### Ticket 5.2.1: Create useNotes hook
- **Description**: Custom hook for notes data access
- **Files to Create**: `src/hooks/useNotes.ts`
- **Acceptance Criteria**:
  - Returns notes, selectedNote, loading state
  - Methods: createNote, updateNote, deleteNote
  - Handles async operations
- **Test Expectations**: Hook provides data access

### Ticket 5.2.2: Create useFolders hook
- **Description**: Custom hook for folders data access
- **Files to Create**: `src/hooks/useFolders.ts`
- **Acceptance Criteria**:
  - Returns folders as tree structure
  - Methods: createFolder, deleteFolder
  - Computes folder paths
- **Test Expectations**: Hook provides folder tree

### Ticket 5.2.3: Create useSearch hook
- **Description**: Custom hook for search functionality
- **Files to Create**: `src/hooks/useSearch.ts`
- **Acceptance Criteria**:
  - Debounced search execution
  - Returns results, isSearching, query
  - Cancels previous search on new query
- **Test Expectations**: Search executes and returns results

---

# EPIC 6: Application Integration

> Wire together all components into a working application.

## Story 6.1: Route Setup

### Ticket 6.1.1: Configure React Router
- **Description**: Set up client-side routing
- **Files to Create**: `src/router/index.tsx`
- **Files to Modify**: `package.json` (add react-router-dom)
- **Acceptance Criteria**:
  - Routes: /, /note/:id, /folder/:id, /search, /settings
  - 404 handling
- **Test Expectations**: Navigation between routes works

### Ticket 6.1.2: Create route components
- **Description**: Create page components for each route
- **Files to Create**:
  - `src/pages/HomePage.tsx`
  - `src/pages/NotePage.tsx`
  - `src/pages/SearchPage.tsx`
  - `src/pages/SettingsPage.tsx`
- **Acceptance Criteria**:
  - Each page renders appropriate content
  - Pages use shared layout
- **Test Expectations**: Pages render without errors

---

## Story 6.2: App Bootstrap

### Ticket 6.2.1: Create main App component
- **Description**: Root application component
- **Files to Create**: `src/App.tsx`
- **Acceptance Criteria**:
  - Wraps app in providers (Router, Store)
  - Renders AppShell layout
  - Handles global error boundary
- **Test Expectations**: App renders without errors

### Ticket 6.2.2: Create application entry point
- **Description**: React DOM render entry
- **Files to Modify**: `src/index.ts` → rename to `src/main.tsx`
- **Files to Create**: `index.html`
- **Acceptance Criteria**:
  - Renders App to #root
  - Imports global styles
- **Test Expectations**: Application starts in browser

### Ticket 6.2.3: Implement data initialization
- **Description**: Load initial data on app start
- **Files to Create**: `src/services/bootstrap.ts`
- **Acceptance Criteria**:
  - Loads notes from storage
  - Loads folders from storage
  - Populates store
  - Shows loading state during init
- **Test Expectations**: App loads with persisted data

---

## Story 6.3: Feature Wiring

### Ticket 6.3.1: Wire note creation flow
- **Description**: Connect new note button to creation logic
- **Files to Modify**: `src/components/layout/Sidebar.tsx`, `src/pages/HomePage.tsx`
- **Acceptance Criteria**:
  - Click "New Note" creates note
  - Navigates to new note
  - Note appears in list
- **Test Expectations**: Full creation flow works

### Ticket 6.3.2: Wire note editing flow
- **Description**: Connect editor to save logic
- **Files to Modify**: `src/components/notes/NoteEditor.tsx`
- **Acceptance Criteria**:
  - Changes auto-saved (debounced 1s)
  - Save indicator shows status
  - Tags extracted and saved
- **Test Expectations**: Edits persist after refresh

### Ticket 6.3.3: Wire search flow
- **Description**: Connect search input to results
- **Files to Modify**: `src/components/layout/Header.tsx`, `src/pages/SearchPage.tsx`
- **Acceptance Criteria**:
  - Typing triggers search
  - Results update live
  - Clicking result opens note
- **Test Expectations**: Search finds and navigates to notes

### Ticket 6.3.4: Wire folder navigation
- **Description**: Connect folder tree to note filtering
- **Files to Modify**: `src/components/navigation/FolderTree.tsx`
- **Acceptance Criteria**:
  - Clicking folder filters note list
  - Breadcrumb updates
  - URL reflects selection
- **Test Expectations**: Folder selection filters correctly

---

# EPIC 7: Styling & Theming

> Implement visual design and theme support.

## Story 7.1: Design System Setup

### Ticket 7.1.1: Configure Tailwind CSS
- **Description**: Set up Tailwind CSS with custom config
- **Files to Create**: `tailwind.config.js`, `postcss.config.js`
- **Files to Modify**: `package.json`
- **Acceptance Criteria**:
  - Tailwind configured
  - Custom colors for brand
  - Dark mode variant enabled
- **Test Expectations**: Tailwind classes apply styles

### Ticket 7.1.2: Create global styles
- **Description**: Base styles and CSS reset
- **Files to Create**: `src/styles/globals.css`
- **Acceptance Criteria**:
  - CSS reset included
  - Typography defaults
  - Tailwind directives imported
- **Test Expectations**: Consistent base styling

### Ticket 7.1.3: Create design tokens
- **Description**: Define color and spacing tokens
- **Files to Create**: `src/styles/tokens.ts`
- **Acceptance Criteria**:
  - Color palette (primary, secondary, neutral)
  - Spacing scale
  - Typography scale
- **Test Expectations**: Tokens importable in components

---

## Story 7.2: Theme Implementation

### Ticket 7.2.1: Implement dark mode toggle
- **Description**: Add dark/light theme switching
- **Files to Create**: `src/hooks/useTheme.ts`
- **Files to Modify**: `src/store/uiSlice.ts`
- **Acceptance Criteria**:
  - Toggle between light/dark
  - Persists preference
  - Respects system preference initially
- **Test Expectations**: Theme toggles visually

### Ticket 7.2.2: Create theme-aware components
- **Description**: Update components for theme support
- **Files to Modify**: All component files
- **Acceptance Criteria**:
  - All components use theme-aware classes
  - No hardcoded colors
- **Test Expectations**: UI correct in both themes

---

# EPIC 8: Testing & Quality

> Ensure application reliability through testing.

## Story 8.1: Unit Tests

### Ticket 8.1.1: Test note validation utilities
- **Description**: Unit tests for validation functions
- **Files to Create**: `tests/utils/noteValidation.test.ts`
- **Acceptance Criteria**:
  - Tests all validation rules
  - Tests edge cases
  - 100% coverage of validation module
- **Test Expectations**: All tests pass

### Ticket 8.1.2: Test markdown parser
- **Description**: Unit tests for markdown processing
- **Files to Create**: `tests/services/markdown.test.ts`
- **Acceptance Criteria**:
  - Tests standard markdown
  - Tests wiki-links
  - Tests tag extraction
- **Test Expectations**: All tests pass

### Ticket 8.1.3: Test link service
- **Description**: Unit tests for link management
- **Files to Create**: `tests/services/linkService.test.ts`
- **Acceptance Criteria**:
  - Tests link extraction
  - Tests backlink calculation
  - Tests broken link detection
- **Test Expectations**: All tests pass

### Ticket 8.1.4: Test store slices
- **Description**: Unit tests for Zustand store
- **Files to Create**: `tests/store/notesSlice.test.ts`
- **Acceptance Criteria**:
  - Tests all actions
  - Tests state transitions
- **Test Expectations**: All tests pass

---

## Story 8.2: Component Tests

### Ticket 8.2.1: Set up React Testing Library
- **Description**: Configure component testing
- **Files to Create**: `tests/setup.ts`
- **Files to Modify**: `vitest.config.ts`
- **Acceptance Criteria**:
  - RTL configured
  - Custom render with providers
  - User event setup
- **Test Expectations**: Test utilities work

### Ticket 8.2.2: Test NoteEditor component
- **Description**: Component tests for note editor
- **Files to Create**: `tests/components/NoteEditor.test.tsx`
- **Acceptance Criteria**:
  - Tests rendering
  - Tests user input
  - Tests save behavior
- **Test Expectations**: All tests pass

### Ticket 8.2.3: Test NoteList component
- **Description**: Component tests for note list
- **Files to Create**: `tests/components/NoteList.test.tsx`
- **Acceptance Criteria**:
  - Tests rendering with notes
  - Tests empty state
  - Tests selection
- **Test Expectations**: All tests pass

---

## Story 8.3: Integration Tests

### Ticket 8.3.1: Test note creation flow
- **Description**: Integration test for creating notes
- **Files to Create**: `tests/integration/noteCreation.test.ts`
- **Acceptance Criteria**:
  - Tests full flow from button click to saved note
  - Verifies storage persistence
- **Test Expectations**: All tests pass

### Ticket 8.3.2: Test search functionality
- **Description**: Integration test for search
- **Files to Create**: `tests/integration/search.test.ts`
- **Acceptance Criteria**:
  - Tests search with results
  - Tests search with no results
  - Tests result navigation
- **Test Expectations**: All tests pass

---

# Dependency Graph

```
EPIC 1 (Foundation)
    ↓
EPIC 2 (Data Layer)
    ↓
EPIC 3 (Core Operations) ←→ EPIC 5 (State Management)
    ↓                              ↓
EPIC 4 (UI Components) ────────────┘
    ↓
EPIC 6 (Integration)
    ↓
EPIC 7 (Styling) [can parallel with EPIC 6]
    ↓
EPIC 8 (Testing) [can start after EPIC 3]
```

## Parallelization Opportunities

- **EPIC 2 & EPIC 4**: Can start UI component skeletons while data layer is built
- **EPIC 7**: Styling can run parallel to EPIC 6 integration
- **EPIC 8**: Testing can begin as soon as modules are complete
- **Within stories**: Multiple independent tickets can be parallelized

---

# Next Step

**Begin implementation with:**

> **Epic 1 → Story 1.1 → Ticket 1.1.1**: Create package.json with project metadata

Once Ticket 1.1.1 is selected, invoke **ORCHESTRATE-FEATURE-LOOP** to begin the implementation cycle.

---

*This backlog represents a complete, production-ready development plan for the SecondaBrain personal knowledge management system. Total estimated tickets: 67. Adjust scope as needed based on MVP requirements.*
