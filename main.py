import os
from urllib import request
from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date, datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Table, Column, Integer, ForeignKey
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from dotenv import load_dotenv

login_manager = LoginManager()
app = Flask(__name__)
load_dotenv(".env")

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)
login_manager.init_app(app)
Base = declarative_base()
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL1", "sqlite:///blog.db")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


##CONFIGURE TABLES
class Users(UserMixin, db.Model):
    __tablename__ = "users"  ##one to many database #parent
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    post = relationship("BlogPost", back_populates="author")

    # *******Add parent relationship*******#
    # "comment_author" refers to the comment_author property in the Comment class.
    comments = relationship("Comment", back_populates="comment_author")


class Comment(db.Model):
    __tablename__ = "comments"

    # *******Add child relationship*******#
    # "users.id" The users refers to the tablename of the Users class.
    # "comments" refers to the comments property in the User class.

    id = db.Column(db.Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey('users.id'))
    comment_author = relationship("Users", back_populates="comments")
    post_id = Column(Integer, ForeignKey('blog_post.id'))
    parent_post = relationship("BlogPost", back_populates="user_comment")
    text = db.Column(db.Text, nullable=False)


class BlogPost(db.Model):
    __tablename__ = "blog_post"  # child
    id = db.Column(db.Integer, primary_key=True)

    author_id = Column(Integer, ForeignKey('users.id'))
    author = relationship("Users", back_populates="post")
    author_api = Column(db.String(250), nullable=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    user_comment = relationship(Comment, back_populates="parent_post")


db.create_all() #update
# Create a function that request new data
import requests


def news_data():
    response = requests.get(os.getenv("NEWS_API"))
    data = response.json()["results"]
    return data


# Class to handle API data
class NewsData:
    def __init__(self, data):
        self.author = data["creator"]
        self.title = data["title"]
        self.subtitle = data["description"]
        self.date = data["pubDate"]
        self.body = data["content"]
        self.img_url = data["image_url"]
        self.link = data["link"]

def data_from_api(data):
    for news in data:
        n = NewsData(news)
        if db.session.query(BlogPost).filter_by(title=n.title).first():
            continue
        else:
            if n.img_url is None:
                n.img_url = "https://images.unsplash.com/photo-1498671546682-94a232c26d17?ixlib=rb-4.0.3&ixid" \
                            "=MnwxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8&auto=format&fit=crop&w=898&q=80 "
            if n.body is None:
                n.body = n.link

            if n.author is None:
                n.author = "unknown"
            format_data = datetime.strptime(n.date.split(" ")[0], "%Y-%m-%d")
            try:
                new_post = BlogPost(
                    title=n.title,
                    subtitle=n.subtitle,
                    body=n.body,
                    img_url=n.img_url,
                    author_api=n.author[0],
                    date=format_data.strftime("%B %d, %Y")
                )
                db.session.add(new_post)
                db.session.commit()
            except:
                continue


def admin_only(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.is_anonymous or current_user.id != 1:
            return abort(403)
        return func(*args, **kwargs)

    return decorated_function


@app.route('/')
def get_all_posts():
    data = news_data()
    data_from_api(data)
    posts = BlogPost.query.order_by(BlogPost.date.desc()).all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["POST", "GET"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if db.session.query(Users).filter_by(email=form.email.data).first():
            flash("You've already signed up with that email, login instead!")
            return redirect(url_for("login"))

        hashed_password = generate_password_hash(form.password.data, method="pbkdf2:sha256", salt_length=8)
        new_user = Users(email=form.email.data,
                         password=hashed_password,
                         name=form.name.data)

        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_all_posts"))

    return render_template("register.html", form=form)


## Login setup
@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(user_id)


@app.route('/login', methods=["POST", "GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(Users).filter_by(email=form.email.data).first()
        if user:
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("Password incorrect, please try again.")
                return redirect(url_for("login"))
        else:
            flash("That email does not exist, please try again.")
            return redirect(url_for("login"))
    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            post_id=post_id,
            comment_author=current_user,  # or just use current_user.name
            text=form.comment.data,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
    return render_template("post.html", post=requested_post, form=form, len=len(requested_post.body))  # comments=comments


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["POST", "GET"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        author = db.session.query(Users).filter_by(name=current_user.name).first()

        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=author,  # Users.query.get(name=current_user),  #
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["POST", "GET"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data
        # post.author = current_user.name
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


# todo: Create a function to delete comments

if __name__ == "__main__":
    app.run(debug=True)
    # app.run(host='0.0.0.0', port=8080,debug=True)
