-- User Data Table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    followers INT DEFAULT 0,
    following INT DEFAULT 0,
    profile_pic TEXT
);

-- Video Metadata Table
CREATE TABLE video_metadata (
    id UUID PRIMARY KEY,
    title VARCHAR(255),
    description TEXT,
    tags JSONB,
    categories JSONB,
    duration INT, -- in seconds
    genre VARCHAR(50),
    uploader_id INT REFERENCES users(id)
);

-- Video Interaction Table
CREATE TABLE video_interactions (
    id SERIAL PRIMARY KEY,
    video_id UUID REFERENCES video_metadata(id),
    views INT DEFAULT 0,
    shares INT DEFAULT 0
);

-- User Interaction Table (for likes/dislikes per user)
CREATE TABLE user_interactions (
    id SERIAL PRIMARY KEY,
    video_interaction_id INT REFERENCES video_interactions(id),
    user_id INT REFERENCES users(id),
    like_dislike SMALLINT DEFAULT 0 CHECK (like_dislike IN (-1, 0, 1)), -- -1 for dislike, 0 for neutral, 1 for like
    UNIQUE (video_interaction_id, user_id) -- Ensure one interaction per user per video
);

-- Comments Table
CREATE TABLE comments (
    id SERIAL PRIMARY KEY,
    video_interaction_id INT REFERENCES video_interactions(id),
    user_id INT REFERENCES users(id),
    comment TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Comment Likes Table
CREATE TABLE comment_likes (
    id SERIAL PRIMARY KEY,
    comment_id INT REFERENCES comments(id),
    user_id INT REFERENCES users(id),
    UNIQUE (comment_id, user_id) -- Ensure one like per user per comment
);

