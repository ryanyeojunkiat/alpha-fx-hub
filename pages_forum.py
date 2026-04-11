import streamlit as st
from datetime import datetime, timedelta
import json

def render_forum():
    """Community Forum with session_state-based posts, likes, and comments."""

    # Initialize session state for forum data
    if "forum_posts" not in st.session_state:
        # Sample posts with realistic trading results
        st.session_state.forum_posts = [
            {
                "id": 1,
                "author": "TradeGod92",
                "timestamp": datetime.now() - timedelta(hours=3),
                "title": "GBP/USD +125 pips this week! Breaking support worked perfectly",
                "content": "Caught the liquidity sweep on GBP/USD yesterday. Price broke the weekly support at 1.2680, swept the lows, then reversed hard. Entered right after the wick rejection on the 1H. Took 1:2.5 R:R on this one. The order block above acted as resistance. Key lesson: patience pays off!",
                "tags": ["PnL Share", "Strategy"],
                "image_url": None,
                "likes": 24,
                "liked_by_user": False,
                "comments": []
            },
            {
                "id": 2,
                "author": "MikeTheTrend",
                "timestamp": datetime.now() - timedelta(hours=6),
                "title": "Question: How do you guys handle multiple timeframe analysis?",
                "content": "I'm trying to improve my entries by using MTF analysis (daily trend + 1H entry). How do you weigh the timeframes? Do you require perfect alignment on all 3, or do you have a hierarchy? Also, do you ignore the 15M entirely or use it for final confirmation?",
                "tags": ["Question"],
                "image_url": None,
                "likes": 8,
                "liked_by_user": False,
                "comments": [
                    {"author": "ChartMaster", "text": "I go Daily (trend) → 4H (structure) → 1H (entry). Don't need perfect alignment, just direction agreement.", "timestamp": datetime.now() - timedelta(hours=5)},
                    {"author": "Alex_FX", "text": "Same here! 15M is noise, stick to the 3.", "timestamp": datetime.now() - timedelta(hours=4)}
                ]
            },
            {
                "id": 3,
                "author": "SarahSwings",
                "timestamp": datetime.now() - timedelta(hours=12),
                "title": "Revenge trading nearly blew my account. Here's what I learned.",
                "content": "Lost 3 trades in a row yesterday. Instead of following my rules, I doubled my position size and went YOLO on a 4-hour chart. Blew $800 in 30 minutes trying to recover my $600 loss. The lesson? When you're emotional, WALK AWAY. I now have a hard rule: if I hit -2% for the day, I'm done. No exceptions. Psychology is 90% of this game.",
                "tags": ["Strategy"],
                "image_url": None,
                "likes": 41,
                "liked_by_user": False,
                "comments": [
                    {"author": "ProTrader", "text": "This deserves a pin. So many people learn this the hard way.", "timestamp": datetime.now() - timedelta(hours=10)},
                    {"author": "NewbieFX", "text": "Thank you for sharing this. I needed to hear it.", "timestamp": datetime.now() - timedelta(hours=8)}
                ]
            },
            {
                "id": 4,
                "author": "DataJunkie",
                "timestamp": datetime.now() - timedelta(hours=24),
                "title": "My winning strategy: BOS + Order Block confluence - 68% WR over 150 trades",
                "content": "Took 150 trades using only BOS (Break of Structure) + Order Block entries on 4H timeframe. Final P&L: +$3,240 (21.6% return). Win rate: 68%. Average R:R: 1:2.1. The key: I only enter when BOTH conditions align. Single condition trades are 55% WR. When combined = 68%. The order block must be recent (within 20 candles) and price must respect it on pullback.",
                "tags": ["PnL Share", "Strategy"],
                "image_url": None,
                "likes": 67,
                "liked_by_user": False,
                "comments": [
                    {"author": "StrategyHunter", "text": "This is the way. Confluence filtering is underrated.", "timestamp": datetime.now() - timedelta(hours=22)},
                ]
            }
        ]

    if "comment_input" not in st.session_state:
        st.session_state.comment_input = {}

    # Cyberpunk styling
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');

    .forum-container {
        font-family: 'Orbitron', monospace;
        background: linear-gradient(135deg, #0a0e27 0%, #16213e 100%);
    }

    .forum-header {
        background: linear-gradient(90deg, #00ff88 0%, #ff0080 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.5em;
        font-weight: 900;
        margin-bottom: 10px;
        text-shadow: 0 0 20px rgba(0, 255, 136, 0.3);
    }

    .post-card {
        background: linear-gradient(135deg, #1a1f3a 0%, #2a1f5a 100%);
        border: 2px solid #00ff88;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 0 20px rgba(0, 255, 136, 0.2), inset 0 0 10px rgba(0, 255, 136, 0.1);
        transition: all 0.3s ease;
    }

    .post-card:hover {
        box-shadow: 0 0 30px rgba(0, 255, 136, 0.4), inset 0 0 15px rgba(0, 255, 136, 0.2);
        transform: translateX(5px);
    }

    .post-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        flex-wrap: wrap;
    }

    .post-author {
        color: #00d4ff;
        font-weight: 700;
        font-size: 1em;
    }

    .post-timestamp {
        color: #888;
        font-size: 0.85em;
    }

    .post-title {
        color: #00ff88;
        font-size: 1.3em;
        font-weight: 700;
        margin-bottom: 10px;
        word-wrap: break-word;
    }

    .post-content {
        color: #e0e0e0;
        line-height: 1.6;
        margin-bottom: 12px;
        word-wrap: break-word;
    }

    .post-tags {
        display: flex;
        gap: 8px;
        margin-bottom: 12px;
        flex-wrap: wrap;
    }

    .tag {
        background: linear-gradient(90deg, #00ff88 0%, #00d4ff 100%);
        color: #0a0e27;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75em;
        font-weight: 700;
    }

    .tag.question {
        background: linear-gradient(90deg, #ff9500 0%, #ff6600 100%);
    }

    .tag.pnl {
        background: linear-gradient(90deg, #00ff88 0%, #00d4ff 100%);
    }

    .post-actions {
        display: flex;
        gap: 12px;
        margin-top: 15px;
        align-items: center;
        flex-wrap: wrap;
    }

    .like-button {
        background: linear-gradient(90deg, #ff0080 0%, #ff0050 100%);
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 700;
        font-size: 0.85em;
        transition: all 0.2s;
    }

    .like-button:hover {
        box-shadow: 0 0 15px rgba(255, 0, 128, 0.6);
        transform: scale(1.05);
    }

    .like-count {
        color: #ff0080;
        font-weight: 700;
        font-size: 0.9em;
    }

    .comment-section {
        background: rgba(0, 255, 136, 0.05);
        border-left: 3px solid #00d4ff;
        padding: 12px;
        margin-top: 15px;
        border-radius: 4px;
    }

    .comment-item {
        background: rgba(0, 0, 0, 0.3);
        border-left: 2px solid #ff0080;
        padding: 10px 12px;
        margin-bottom: 8px;
        border-radius: 4px;
    }

    .comment-author {
        color: #00ff88;
        font-weight: 700;
        font-size: 0.9em;
    }

    .comment-text {
        color: #e0e0e0;
        margin: 4px 0;
        font-size: 0.9em;
    }

    .comment-time {
        color: #666;
        font-size: 0.75em;
    }

    .create-post-box {
        background: linear-gradient(135deg, #3a1a2a 0%, #5a2a3a 100%);
        border: 2px solid #ff0080;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 30px;
        box-shadow: 0 0 20px rgba(255, 0, 128, 0.2);
    }

    .create-post-title {
        color: #ff0080;
        font-weight: 700;
        font-size: 1.2em;
        margin-bottom: 15px;
    }

    .input-field {
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid #00d4ff;
        border-radius: 4px;
        color: #e0e0e0;
        padding: 10px;
        margin-bottom: 10px;
        width: 100%;
        font-family: 'Orbitron', monospace;
    }

    .input-field:focus {
        outline: none;
        border-color: #00ff88;
        box-shadow: 0 0 10px rgba(0, 255, 136, 0.3);
    }

    .submit-button {
        background: linear-gradient(90deg, #00ff88 0%, #00d4ff 100%);
        color: #0a0e27;
        border: none;
        padding: 10px 20px;
        border-radius: 6px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.2s;
        font-family: 'Orbitron', monospace;
    }

    .submit-button:hover {
        box-shadow: 0 0 20px rgba(0, 255, 136, 0.5);
        transform: scale(1.05);
    }

    .comment-button {
        background: linear-gradient(90deg, #00d4ff 0%, #00ff88 100%);
        color: #0a0e27;
        border: none;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: 700;
        cursor: pointer;
        font-size: 0.8em;
        transition: all 0.2s;
    }

    .comment-button:hover {
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.5);
    }

    .stats-row {
        display: flex;
        gap: 15px;
        margin-bottom: 20px;
        flex-wrap: wrap;
    }

    .stat-box {
        background: linear-gradient(135deg, #1a1f3a 0%, #2a1f5a 100%);
        border: 2px solid #00d4ff;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        color: #00ff88;
        font-weight: 700;
        min-width: 140px;
    }

    .stat-number {
        font-size: 2em;
        color: #ff0080;
    }

    .stat-label {
        font-size: 0.8em;
        color: #00d4ff;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="forum-header">💬 TRADING FORUM</div>', unsafe_allow_html=True)
    st.markdown('<div style="color: #00d4ff; margin-bottom: 20px; font-size: 0.9em;">Share setups, ask questions, celebrate wins with the community</div>', unsafe_allow_html=True)

    # Forum stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-box"><div class="stat-number">{len(st.session_state.forum_posts)}</div><div class="stat-label">Posts</div></div>', unsafe_allow_html=True)
    with col2:
        total_comments = sum(len(post["comments"]) for post in st.session_state.forum_posts)
        st.markdown(f'<div class="stat-box"><div class="stat-number">{total_comments}</div><div class="stat-label">Comments</div></div>', unsafe_allow_html=True)
    with col3:
        total_likes = sum(post["likes"] for post in st.session_state.forum_posts)
        st.markdown(f'<div class="stat-box"><div class="stat-number">{total_likes}</div><div class="stat-label">Likes</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-box"><div class="stat-number">247</div><div class="stat-label">Members</div></div>', unsafe_allow_html=True)

    st.divider()

    # Create post section
    with st.expander("📝 Create New Post", expanded=False):
        st.markdown('<div class="create-post-box">', unsafe_allow_html=True)

        post_title = st.text_input("Post Title", placeholder="Share your win, ask a question, discuss a strategy...", key="post_title_input")
        post_content = st.text_area("Post Content", placeholder="Tell your story...", height=120, key="post_content_input")
        post_image = st.text_input("Image URL (optional)", placeholder="https://example.com/image.png", key="post_image_input")

        col1, col2, col3 = st.columns(3)
        with col1:
            tag_pnl = st.checkbox("PnL Share", key="tag_pnl")
        with col2:
            tag_strategy = st.checkbox("Strategy", key="tag_strategy")
        with col3:
            tag_question = st.checkbox("Question", key="tag_question")

        if st.button("Post to Forum", key="submit_post"):
            if post_title and post_content:
                tags = []
                if tag_pnl:
                    tags.append("PnL Share")
                if tag_strategy:
                    tags.append("Strategy")
                if tag_question:
                    tags.append("Question")

                new_post = {
                    "id": max([p["id"] for p in st.session_state.forum_posts], default=0) + 1,
                    "author": "You",
                    "timestamp": datetime.now(),
                    "title": post_title,
                    "content": post_content,
                    "tags": tags if tags else ["General"],
                    "image_url": post_image if post_image else None,
                    "likes": 0,
                    "liked_by_user": False,
                    "comments": []
                }

                st.session_state.forum_posts.insert(0, new_post)
                st.success("✓ Post created! Refresh to see it in the feed.")
                st.rerun()
            else:
                st.error("Please fill in title and content.")

        st.markdown('</div>', unsafe_allow_html=True)

    st.divider()

    # Display posts
    st.markdown('<div style="color: #00ff88; font-weight: 700; margin-bottom: 20px; font-size: 1.2em;">📰 Recent Activity</div>', unsafe_allow_html=True)

    for post in st.session_state.forum_posts:
        st.markdown('<div class="post-card">', unsafe_allow_html=True)

        # Post header
        col1, col2 = st.columns([0.7, 0.3])
        with col1:
            st.markdown(f'<div class="post-author">@{post["author"]}</div>', unsafe_allow_html=True)
        with col2:
            time_diff = datetime.now() - post["timestamp"]
            if time_diff.days > 0:
                time_str = f"{time_diff.days}d ago"
            elif time_diff.seconds > 3600:
                time_str = f"{time_diff.seconds // 3600}h ago"
            else:
                time_str = f"{time_diff.seconds // 60}m ago"
            st.markdown(f'<div class="post-timestamp">{time_str}</div>', unsafe_allow_html=True)

        # Title
        st.markdown(f'<div class="post-title">{post["title"]}</div>', unsafe_allow_html=True)

        # Tags
        st.markdown('<div class="post-tags">', unsafe_allow_html=True)
        for tag in post["tags"]:
            tag_class = "question" if tag == "Question" else ("pnl" if tag == "PnL Share" else "")
            st.markdown(f'<span class="tag {tag_class}">{tag}</span>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Content
        st.markdown(f'<div class="post-content">{post["content"]}</div>', unsafe_allow_html=True)

        # Image if provided
        if post["image_url"]:
            try:
                st.image(post["image_url"], use_column_width=True)
            except:
                st.markdown(f'<div style="color: #888; font-size: 0.85em;">Image: {post["image_url"]}</div>', unsafe_allow_html=True)

        # Actions
        st.markdown('<div class="post-actions">', unsafe_allow_html=True)

        col1, col2 = st.columns([0.2, 0.8])
        with col1:
            like_key = f"like_{post['id']}"
            if st.button(f"❤️ {post['likes']}", key=like_key):
                if not post["liked_by_user"]:
                    post["likes"] += 1
                    post["liked_by_user"] = True
                else:
                    post["likes"] -= 1
                    post["liked_by_user"] = False
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        # Comments section
        if post["comments"] or True:  # Always show comment section
            st.markdown('<div class="comment-section">', unsafe_allow_html=True)
            st.markdown(f'<div style="color: #00ff88; font-weight: 700; margin-bottom: 10px;">Comments ({len(post["comments"])})</div>', unsafe_allow_html=True)

            # Display existing comments
            for i, comment in enumerate(post["comments"]):
                st.markdown('<div class="comment-item">', unsafe_allow_html=True)
                st.markdown(f'<div class="comment-author">{comment["author"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="comment-text">{comment["text"]}</div>', unsafe_allow_html=True)
                time_diff = datetime.now() - comment["timestamp"]
                if time_diff.days > 0:
                    time_str = f"{time_diff.days}d ago"
                elif time_diff.seconds > 3600:
                    time_str = f"{time_diff.seconds // 3600}h ago"
                else:
                    time_str = f"{time_diff.seconds // 60}m ago"
                st.markdown(f'<div class="comment-time">{time_str}</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            # Add comment input
            col1, col2 = st.columns([0.85, 0.15])
            with col1:
                comment_key = f"comment_input_{post['id']}"
                comment_text = st.text_input("Add a comment...", key=comment_key, placeholder="Share your thoughts...")
            with col2:
                if st.button("Post", key=f"comment_submit_{post['id']}"):
                    if comment_text:
                        post["comments"].append({
                            "author": "You",
                            "text": comment_text,
                            "timestamp": datetime.now()
                        })
                        st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("")  # Spacing


if __name__ == "__main__":
    render_forum()
