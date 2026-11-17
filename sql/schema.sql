-- =====================================================================
-- Reelmap: content idea and storyboard planner for UGC creators
-- Database schema (MySQL 8 / MariaDB 10.6+), normalised to 3NF
-- =====================================================================
-- Drop in reverse dependency order so the script can be re-run.
DROP VIEW  IF EXISTS v_project_summary;
DROP TABLE IF EXISTS downloads;
DROP TABLE IF EXISTS storyboard_frames;
DROP TABLE IF EXISTS ideas;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS scene_templates;
DROP TABLE IF EXISTS idea_templates;
DROP TABLE IF EXISTS content_formats;
DROP TABLE IF EXISTS niches;
DROP TABLE IF EXISTS users;

-- People who use the system. The first account created becomes the admin.
CREATE TABLE users (
    user_id        INT AUTO_INCREMENT PRIMARY KEY,
    full_name      VARCHAR(80)  NOT NULL,
    email          VARCHAR(120) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    role           ENUM('creator','admin') NOT NULL DEFAULT 'creator',
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Content categories, e.g. Fitness, Food & Cooking.
CREATE TABLE niches (
    niche_id     INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(50)  NOT NULL UNIQUE,
    description  VARCHAR(200) NOT NULL
) ENGINE=InnoDB;

-- UGC video styles, e.g. Product Review, Day in My Life.
CREATE TABLE content_formats (
    format_id         INT AUTO_INCREMENT PRIMARY KEY,
    name              VARCHAR(50)  NOT NULL UNIQUE,
    style             ENUM('on_camera','faceless','product') NOT NULL,
    description       VARCHAR(200) NOT NULL,
    icon_pose         VARCHAR(20)  NOT NULL DEFAULT 'stand',
    default_duration  SMALLINT     NOT NULL DEFAULT 30
) ENGINE=InnoDB;

-- The idea bank. niche_id NULL means the template suits every niche.
-- Placeholders: {topic}, {Topic}, {audience}, {niche}, {platform}
CREATE TABLE idea_templates (
    template_id           INT AUTO_INCREMENT PRIMARY KEY,
    format_id             INT NOT NULL,
    niche_id              INT NULL,
    title_template        VARCHAR(150) NOT NULL,
    hook_template         VARCHAR(200) NOT NULL,
    description_template  VARCHAR(400) NOT NULL,
    difficulty            ENUM('easy','medium','hard') NOT NULL DEFAULT 'easy',
    is_active             TINYINT(1) NOT NULL DEFAULT 1,
    created_by            INT NULL,
    CONSTRAINT fk_tpl_format FOREIGN KEY (format_id) REFERENCES content_formats(format_id) ON DELETE CASCADE,
    CONSTRAINT fk_tpl_niche  FOREIGN KEY (niche_id)  REFERENCES niches(niche_id) ON DELETE SET NULL,
    CONSTRAINT fk_tpl_user   FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- The scene plan used to build a storyboard for each format.
CREATE TABLE scene_templates (
    scene_template_id  INT AUTO_INCREMENT PRIMARY KEY,
    format_id          INT NOT NULL,
    scene_order        TINYINT NOT NULL,
    shot_type          ENUM('wide','medium','close_up') NOT NULL,
    pose               ENUM('stand','wave','talk','point','think','hold_phone','hold_product',
                            'thumbs_up','excited','sit_laptop','walk','shrug') NOT NULL,
    prop               ENUM('none','phone','product','laptop','speech','sparkle','arrow',
                            'before_after','mirror','cup') NOT NULL DEFAULT 'none',
    action_template    VARCHAR(200) NOT NULL,
    dialogue_template  VARCHAR(200) NOT NULL,
    text_template      VARCHAR(80)  NOT NULL,
    duration_sec       TINYINT NOT NULL DEFAULT 5,
    CONSTRAINT fk_scene_format FOREIGN KEY (format_id) REFERENCES content_formats(format_id) ON DELETE CASCADE,
    CONSTRAINT uq_scene UNIQUE (format_id, scene_order)
) ENGINE=InnoDB;

-- A content plan a user is working on.
CREATE TABLE projects (
    project_id       INT AUTO_INCREMENT PRIMARY KEY,
    user_id          INT NOT NULL,
    niche_id         INT NOT NULL,
    format_id        INT NOT NULL,
    title            VARCHAR(120) NOT NULL,
    topic            VARCHAR(150) NOT NULL,
    platform         ENUM('Instagram Reels','YouTube Shorts','Facebook Reels','LinkedIn Video') NOT NULL,
    target_audience  VARCHAR(120) NOT NULL,
    status           ENUM('draft','planned','filmed','posted') NOT NULL DEFAULT 'draft',
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_proj_user   FOREIGN KEY (user_id)   REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_proj_niche  FOREIGN KEY (niche_id)  REFERENCES niches(niche_id),
    CONSTRAINT fk_proj_format FOREIGN KEY (format_id) REFERENCES content_formats(format_id),
    INDEX idx_proj_user (user_id, updated_at)
) ENGINE=InnoDB;

-- Ideas generated for a project (from the idea bank or from AI).
CREATE TABLE ideas (
    idea_id      INT AUTO_INCREMENT PRIMARY KEY,
    project_id   INT NOT NULL,
    template_id  INT NULL,
    title        VARCHAR(150) NOT NULL,
    hook         VARCHAR(200) NOT NULL,
    description  VARCHAR(500) NOT NULL,
    source       ENUM('bank','ai') NOT NULL DEFAULT 'bank',
    is_selected  TINYINT(1) NOT NULL DEFAULT 0,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_idea_project  FOREIGN KEY (project_id)  REFERENCES projects(project_id) ON DELETE CASCADE,
    CONSTRAINT fk_idea_template FOREIGN KEY (template_id) REFERENCES idea_templates(template_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- One row per storyboard frame of an idea.
CREATE TABLE storyboard_frames (
    frame_id        INT AUTO_INCREMENT PRIMARY KEY,
    idea_id         INT NOT NULL,
    frame_no        TINYINT NOT NULL,
    shot_type       ENUM('wide','medium','close_up') NOT NULL,
    pose            ENUM('stand','wave','talk','point','think','hold_phone','hold_product',
                         'thumbs_up','excited','sit_laptop','walk','shrug') NOT NULL,
    prop            ENUM('none','phone','product','laptop','speech','sparkle','arrow',
                         'before_after','mirror','cup') NOT NULL DEFAULT 'none',
    action_text     VARCHAR(250) NOT NULL,
    dialogue        VARCHAR(250) NOT NULL,
    on_screen_text  VARCHAR(80)  NOT NULL DEFAULT '',
    duration_sec    TINYINT NOT NULL DEFAULT 5,
    CONSTRAINT fk_frame_idea FOREIGN KEY (idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE,
    CONSTRAINT uq_frame UNIQUE (idea_id, frame_no),
    CONSTRAINT chk_duration CHECK (duration_sec BETWEEN 1 AND 60)
) ENGINE=InnoDB;

-- Log of PDF downloads: a many-to-many link between users and ideas.
CREATE TABLE downloads (
    download_id    INT AUTO_INCREMENT PRIMARY KEY,
    user_id        INT NOT NULL,
    idea_id        INT NOT NULL,
    downloaded_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_dl_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_dl_idea FOREIGN KEY (idea_id) REFERENCES ideas(idea_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Summary view used by the Projects page (joins + aggregates).
CREATE VIEW v_project_summary AS
SELECT  p.project_id, p.user_id, p.title, p.topic, p.platform, p.status, p.updated_at,
        n.name AS niche, f.name AS format_name,
        COUNT(DISTINCT i.idea_id)  AS idea_count,
        COUNT(DISTINCT sf.idea_id) AS storyboard_count
FROM projects p
JOIN niches n          ON n.niche_id  = p.niche_id
JOIN content_formats f ON f.format_id = p.format_id
LEFT JOIN ideas i      ON i.project_id = p.project_id
LEFT JOIN storyboard_frames sf ON sf.idea_id = i.idea_id
GROUP BY p.project_id, p.user_id, p.title, p.topic, p.platform, p.status, p.updated_at, n.name, f.name;
