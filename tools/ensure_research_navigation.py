#!/usr/bin/env python3
"""Public navigation guard.

The top page is now an explicit portal with three JRA main-race entry pages
(this week / future schedule / past results) plus research pages.

The previous automatic HTML rewriter is intentionally retired because it could
silently restore the old anchor-link navigation and overwrite the portal layout.
Detailed pages already contain explicit "トップページに戻る" links and are
maintained directly in their source files.
"""

print('Navigation is managed directly; no automatic rewrite required.')
