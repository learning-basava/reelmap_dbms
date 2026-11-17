-- =====================================================================
-- Reelmap: sample SQL queries used by the application
-- (%s marks are filled in safely by PyMySQL at run time)
-- =====================================================================

-- ---------- CREATE (INSERT) ----------
-- Sign up a new user (password is stored as a hash, never in plain text)
INSERT INTO users (full_name, email, password_hash, role)
VALUES ('Asha Rao', 'asha@example.com', 'pbkdf2:sha256:...', 'creator');

-- Create a content plan
INSERT INTO projects (user_id, niche_id, format_id, title, topic, platform, target_audience)
VALUES (1, 2, 4, 'Home workout videos', 'home workout', 'Instagram Reels', 'college students');

-- Log a PDF download
INSERT INTO downloads (user_id, idea_id) VALUES (1, 1);

-- ---------- READ (SELECT) ----------
-- Log in: find the user by email
SELECT user_id, password_hash FROM users WHERE email = 'asha@example.com';

-- Pick 5 unused idea templates for a project: niche-specific first, then general (subquery + ORDER BY)
SELECT t.template_id, t.title_template, t.hook_template
FROM idea_templates t
WHERE t.format_id = 4 AND t.is_active = 1
  AND (t.niche_id = 2 OR t.niche_id IS NULL)
  AND t.template_id NOT IN (SELECT i.template_id FROM ideas i
                            WHERE i.project_id = 1 AND i.template_id IS NOT NULL)
ORDER BY (t.niche_id IS NULL), RAND()
LIMIT 5;

-- Project details with niche and format names (INNER JOIN)
SELECT p.*, n.name AS niche, f.name AS format_name
FROM projects p
JOIN niches n          ON n.niche_id = p.niche_id
JOIN content_formats f ON f.format_id = p.format_id
WHERE p.project_id = 1 AND p.user_id = 1;

-- Ideas of a project with the number of storyboard frames (LEFT JOIN + GROUP BY)
SELECT i.idea_id, i.title, COUNT(sf.frame_id) AS frame_count
FROM ideas i
LEFT JOIN storyboard_frames sf ON sf.idea_id = i.idea_id
WHERE i.project_id = 1
GROUP BY i.idea_id, i.title;

-- Dashboard numbers (scalar subqueries + COUNT)
SELECT (SELECT COUNT(*) FROM projects WHERE user_id = 1) AS projects,
       (SELECT COUNT(*) FROM ideas i JOIN projects p ON p.project_id = i.project_id WHERE p.user_id = 1) AS ideas,
       (SELECT COUNT(*) FROM downloads WHERE user_id = 1) AS downloads;

-- Plans per status (GROUP BY)
SELECT status, COUNT(*) AS n FROM projects WHERE user_id = 1 GROUP BY status;

-- Search plans by keyword, niche and status (uses the view, LIKE)
SELECT * FROM v_project_summary
WHERE user_id = 1 AND (title LIKE '%phone%' OR topic LIKE '%phone%') AND status = 'planned'
ORDER BY updated_at DESC;

-- Idea bank usage report: how often each template was used (multi-table LEFT JOIN + aggregate)
SELECT t.template_id, t.title_template, f.name AS format_name,
       COALESCE(n.name, 'All niches') AS niche_name, COUNT(i.idea_id) AS times_used
FROM idea_templates t
JOIN content_formats f ON f.format_id = t.format_id
LEFT JOIN niches n     ON n.niche_id = t.niche_id
LEFT JOIN ideas i      ON i.template_id = t.template_id
GROUP BY t.template_id, t.title_template, f.name, n.name
ORDER BY times_used DESC;

-- Total video length per storyboard (SUM)
SELECT idea_id, COUNT(*) AS scenes, SUM(duration_sec) AS total_seconds
FROM storyboard_frames GROUP BY idea_id HAVING COUNT(*) >= 3;

-- ---------- UPDATE ----------
UPDATE projects SET status = 'filmed' WHERE project_id = 1 AND user_id = 1;

UPDATE storyboard_frames
SET pose = 'excited', prop = 'sparkle', on_screen_text = 'You only need a mat', duration_sec = 6
WHERE frame_id = 2;

UPDATE idea_templates SET is_active = 1 - is_active WHERE template_id = 5;

-- ---------- DELETE ----------
-- Deleting a project also deletes its ideas, frames and downloads (ON DELETE CASCADE)
DELETE FROM projects WHERE project_id = 1 AND user_id = 1;

DELETE FROM storyboard_frames WHERE frame_id = 7;
