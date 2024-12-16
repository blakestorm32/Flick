from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from pymongo import MongoClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from bson.objectid import ObjectId
from io import BytesIO
from gridfs import GridFS

app = FastAPI()

# MongoDB setup
MONGO_URI = "mongodb://root:example@mongo:27017/"
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["video_db"]
fs = GridFS(mongo_db)

# PostgreSQL setup
POSTGRES_URI = "postgresql+asyncpg://postgres:password@postgres:5432/videoplatform"
engine = create_async_engine(POSTGRES_URI, echo=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@app.post("/upload_video/")
async def upload_video(
    video: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(...),
    tags: str = Form(...),
    categories: str = Form(...),
    duration: int = Form(...),
    genre: str = Form(...),
    username: str = Form(...),
):
    async with AsyncSessionLocal() as session:
        try:
            # Save video in MongoDB
            video_data = await video.read()
            video_id = fs.put(video_data, filename=video.filename)

            # Insert video metadata into PostgreSQL
            metadata_query = text(
                """
                INSERT INTO video_metadata (id, title, description, tags, categories, duration, genre)
                VALUES (:id, :title, :description, :tags, :categories, :duration, :genre)
                """
            )
            await session.execute(
                metadata_query,
                {
                    "id": str(video_id),
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categories": categories,
                    "duration": duration,
                    "genre": genre,
                },
            )

            # Add video to user's video list
            user_query = text("UPDATE users SET videos = videos || :video_id WHERE username = :username")
            await session.execute(user_query, {"video_id": f'"{str(video_id)}"', "username": username})

            await session.commit()
            return {"message": "Video uploaded successfully", "video_id": str(video_id)}
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@app.get("/watched_videos/{username}")
async def get_watched_videos(username: str):
    async with AsyncSessionLocal() as session:
        try:
            # Fetch watched video IDs
            watched_query = text("SELECT video_id FROM user_interactions WHERE user_id = (SELECT id FROM users WHERE username = :username)")
            result = await session.execute(watched_query, {"username": username})
            watched_videos = [row["video_id"] for row in result.fetchall()]
            return {"username": username, "watched_videos": watched_videos}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.post("/upload_video/")
async def upload_video(
    video: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(...),
    user: str = Form(...),
):
    try:
        # Read video data
        video_data = await video.read()

        # Store video in GridFS
        video_id = fs.put(video_data, filename=video.filename)

        return {"message": "Video uploaded successfully", "video_id": str(video_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.get("/download_video/{video_id}")
async def download_video(video_id: str):
    try:
        # Retrieve the video file from GridFS
        video_file = fs.get(ObjectId(video_id))

        # Function to yield video data in chunks
        def stream_video():
            chunk_size = 1024 * 1024  # 1 MB chunks
            while True:
                data = video_file.read(chunk_size)
                if not data:
                    break
                yield data

        # Return the video stream with appropriate headers
        return StreamingResponse(
            stream_video(),
            media_type="video/mp4",
            headers={"Content-Disposition": f"attachment; filename={video_file.filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


@app.post("/video_interaction/")
async def add_video_interaction(video_id: str):
    async with AsyncSessionLocal() as session:
        try:
            # Add an interaction record for the video
            interaction_query = text(
                "INSERT INTO video_interactions (video_id) VALUES (:video_id) RETURNING id"
            )
            result = await session.execute(interaction_query, {"video_id": video_id})
            interaction_id = result.scalar()

            await session.commit()
            return {"message": "Interaction created", "interaction_id": interaction_id}
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@app.post("/add_comment/")
async def add_comment(video_id: str, user_id: int, comment: str):
    async with AsyncSessionLocal() as session:
        try:
            # Get video interaction ID
            interaction_query = text(
                "SELECT id FROM video_interactions WHERE video_id = :video_id"
            )
            result = await session.execute(interaction_query, {"video_id": video_id})
            interaction_id = result.scalar()

            if not interaction_id:
                raise HTTPException(status_code=404, detail="Video interaction not found")

            # Add comment to the database
            comment_query = text(
                """
                INSERT INTO comments (video_interaction_id, user_id, comment)
                VALUES (:interaction_id, :user_id, :comment)
                RETURNING id
                """
            )
            result = await session.execute(
                comment_query,
                {"interaction_id": interaction_id, "user_id": user_id, "comment": comment},
            )
            comment_id = result.scalar()

            await session.commit()
            return {"message": "Comment added", "comment_id": comment_id}
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@app.post("/like_dislike_video/")
async def like_dislike_video(video_id: str, user_id: int, like_dislike: int):
    async with AsyncSessionLocal() as session:
        try:
            # Get video interaction ID
            interaction_query = text(
                "SELECT id FROM video_interactions WHERE video_id = :video_id"
            )
            result = await session.execute(interaction_query, {"video_id": video_id})
            interaction_id = result.scalar()

            if not interaction_id:
                raise HTTPException(status_code=404, detail="Video interaction not found")

            # Add or update user interaction
            interaction_upsert = text(
                """
                INSERT INTO user_interactions (video_interaction_id, user_id, like_dislike)
                VALUES (:interaction_id, :user_id, :like_dislike)
                ON CONFLICT (video_interaction_id, user_id)
                DO UPDATE SET like_dislike = EXCLUDED.like_dislike
                """
            )
            await session.execute(
                interaction_upsert,
                {
                    "interaction_id": interaction_id,
                    "user_id": user_id,
                    "like_dislike": like_dislike,
                },
            )

            await session.commit()
            return {"message": "Interaction updated"}
        except Exception as e:
            await session.rollback()
            raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@app.get("/video_interactions/{video_id}")
async def get_video_interactions(video_id: str):
    async with AsyncSessionLocal() as session:
        try:
            # Fetch aggregated interactions
            interaction_query = text(
                """
                SELECT vi.views, vi.shares, 
                       COALESCE(SUM(CASE WHEN ui.like_dislike = 1 THEN 1 ELSE 0 END), 0) AS likes,
                       COALESCE(SUM(CASE WHEN ui.like_dislike = -1 THEN 1 ELSE 0 END), 0) AS dislikes
                FROM video_interactions vi
                LEFT JOIN user_interactions ui ON vi.id = ui.video_interaction_id
                WHERE vi.video_id = :video_id
                GROUP BY vi.id
                """
            )
            result = await session.execute(interaction_query, {"video_id": video_id})
            interactions = result.fetchone()

            # Fetch comments
            comments_query = text(
                """
                SELECT c.id, c.comment, c.user_id, c.timestamp, 
                       COALESCE(COUNT(cl.id), 0) AS likes
                FROM comments c
                LEFT JOIN comment_likes cl ON c.id = cl.comment_id
                WHERE c.video_interaction_id = (SELECT id FROM video_interactions WHERE video_id = :video_id)
                GROUP BY c.id
                ORDER BY c.timestamp DESC
                """
            )
            comments = await session.execute(comments_query, {"video_id": video_id})
            comments_list = [
                {
                    "id": row["id"],
                    "comment": row["comment"],
                    "user_id": row["user_id"],
                    "timestamp": row["timestamp"],
                    "likes": row["likes"],
                }
                for row in comments.fetchall()
            ]

            return {"interactions": interactions, "comments": comments_list}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@app.post("/add_user/")
async def add_user(username: str, description: str = "", profile_pic: str = ""):
    async with AsyncSessionLocal() as session:
        try:
            # Insert a new user into the database
            user_query = text(
                """
                INSERT INTO users (username, description, profile_pic)
                VALUES (:username, :description, :profile_pic)
                RETURNING id
                """
            )
            result = await session.execute(
                user_query, {"username": username, "description": description, "profile_pic": profile_pic}
            )
            user_id = result.scalar()

            await session.commit()
            return {"message": "User added successfully", "user_id": user_id}
        except Exception as e:
            await session.rollback()
            if "unique constraint" in str(e).lower():
                raise HTTPException(status_code=400, detail="Username already exists.")
            raise HTTPException(status_code=500, detail=f"An error occurred: {e}")
