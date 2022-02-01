from files.mail import *
from files.__main__ import app, limiter, mail
from files.helpers.alerts import *
from files.helpers.const import *
from files.classes.award import AWARDS
from sqlalchemy import func
from os import path
import calendar
import matplotlib.pyplot as plt
from files.classes.mod_logs import ACTIONTYPES, ACTIONTYPES2
from files.classes.badges import BadgeDef

@app.get("/privacy")
@auth_required
def privacy(v):
	return render_template("privacy.html", v=v)

@app.get("/marseys")
@auth_required
def marseys(v):
	if request.host == 'rdrama.net':
		marseys = g.db.query(Marsey, User).join(User, User.id==Marsey.author_id).order_by(Marsey.count.desc())
	else:
		marseys = g.db.query(Marsey).order_by(Marsey.count.desc())
	return render_template("marseys.html", v=v, marseys=marseys)

@app.get("/marsey_list")
@cache.memoize(timeout=600)
def marsey_list():
	if request.host == 'rdrama.net':
		marseys = [f"{x.name} : {y} {x.tags}" for x, y in g.db.query(Marsey, User.username).join(User, User.id==Marsey.author_id).order_by(Marsey.count.desc())]
	else:
		marseys = [f"{x.name} : {x.tags}" for x in g.db.query(Marsey).order_by(Marsey.count.desc())]

	return str(marseys).replace("'",'"')

@app.get("/terms")
@app.get("/logged_out/terms")
@auth_desired
def terms(v):
	if not v and not request.path.startswith('/logged_out'): return redirect(f"{SITE_FULL}/logged_out{request.full_path}")
	if v and request.path.startswith('/logged_out'): v = None

	return render_template("terms.html", v=v)

@app.get('/sidebar')
@app.get('/logged_out/sidebar')
@auth_desired
def sidebar(v):
	if not v and not request.path.startswith('/logged_out'): return redirect(f"{SITE_FULL}/logged_out{request.full_path}")
	if v and request.path.startswith('/logged_out'): v = None

	return render_template('sidebar.html', v=v)


@app.get("/stats")
@auth_required
def participation_stats(v):

	return render_template("admin/content_stats.html", v=v, title="Content Statistics", data=stats())


@cache.memoize(timeout=86400)
def stats():
	day = int(time.time()) - 86400

	return {"marseys": g.db.query(Marsey.name).count(),
			"users": g.db.query(User.id).count(),
			"private_users": g.db.query(User.id).filter_by(is_private=True).count(),
			"banned_users": g.db.query(User.id).filter(User.is_banned > 0).count(),
			"verified_email_users": g.db.query(User.id).filter_by(is_activated=True).count(),
			"coins_in_circulation": g.db.query(func.sum(User.coins)).scalar(),
			"total_shop_sales": g.db.query(func.sum(User.coins_spent)).scalar(),
			"signups_last_24h": g.db.query(User.id).filter(User.created_utc > day).count(),
			"total_posts": g.db.query(Submission.id).count(),
			"posting_users": g.db.query(Submission.author_id).distinct().count(),
			"listed_posts": g.db.query(Submission.id).filter_by(is_banned=False).filter(Submission.deleted_utc == 0).count(),
			"removed_posts": g.db.query(Submission.id).filter_by(is_banned=True).count(),
			"deleted_posts": g.db.query(Submission.id).filter(Submission.deleted_utc > 0).count(),
			"posts_last_24h": g.db.query(Submission.id).filter(Submission.created_utc > day).count(),
			"total_comments": g.db.query(Comment.id).filter(Comment.author_id.notin_((AUTOJANNY_ID,NOTIFICATIONS_ID))).count(),
			"commenting_users": g.db.query(Comment.author_id).distinct().count(),
			"removed_comments": g.db.query(Comment.id).filter_by(is_banned=True).count(),
			"deleted_comments": g.db.query(Comment.id).filter(Comment.deleted_utc > 0).count(),
			"comments_last_24h": g.db.query(Comment.id).filter(Comment.created_utc > day, Comment.author_id.notin_((AUTOJANNY_ID,NOTIFICATIONS_ID))).count(),
			"post_votes": g.db.query(Vote.id).count(),
			"post_voting_users": g.db.query(Vote.user_id).distinct().count(),
			"comment_votes": g.db.query(CommentVote.id).count(),
			"comment_voting_users": g.db.query(CommentVote.user_id).distinct().count(),
			"total_upvotes": g.db.query(Vote.id).filter_by(vote_type=1).count() + g.db.query(CommentVote.id).filter_by(vote_type=1).count(),
			"total_downvotes": g.db.query(Vote.id).filter_by(vote_type=-1).count() + g.db.query(CommentVote.id).filter_by(vote_type=-1).count(),
			"total_awards": g.db.query(AwardRelationship.id).count(),
			"awards_given": g.db.query(AwardRelationship.id).filter(or_(AwardRelationship.submission_id != None, AwardRelationship.comment_id != None)).count()
			}

@app.get("/chart")
@auth_required
def chart(v):
	days = int(request.values.get("days", 0))
	file = cached_chart(days)
	return send_file(file)


@cache.memoize(timeout=86400)
def cached_chart(days):
	now = time.gmtime()
	midnight_this_morning = time.struct_time((now.tm_year,
											  now.tm_mon,
											  now.tm_mday,
											  0,
											  0,
											  0,
											  now.tm_wday,
											  now.tm_yday,
											  0)
											 )
	today_cutoff = calendar.timegm(midnight_this_morning)

	if not days:
		firstsignup = g.db.query(User.created_utc).filter(User.created_utc != 0).order_by(User.created_utc).first()[0] - 86400
		nowstamp = int(time.time())
		days = int((nowstamp - firstsignup) / 86400)

	if days > 31:
		file = "/weekly_chart.png"
		day_cutoffs = [today_cutoff - 86400 * 7 * i for i in range(35)][1:]
	else:
		file = "/daily_chart.png"
		day_cutoffs = [today_cutoff - 86400 * i for i in range(35)][1:]

	day_cutoffs.insert(0, calendar.timegm(now))

	daily_times = [time.strftime("%d/%m", time.gmtime(day_cutoffs[i + 1])) for i in range(len(day_cutoffs) - 1)][::-1]

	daily_signups = [g.db.query(User.id).filter(User.created_utc < day_cutoffs[i], User.created_utc > day_cutoffs[i + 1]).count() for i in range(len(day_cutoffs) - 1)][::-1]

	post_stats = [g.db.query(Submission.id).filter(Submission.created_utc < day_cutoffs[i], Submission.created_utc > day_cutoffs[i + 1], Submission.is_banned == False).count() for i in range(len(day_cutoffs) - 1)][::-1]

	comment_stats = [g.db.query(Comment.id).filter(Comment.created_utc < day_cutoffs[i], Comment.created_utc > day_cutoffs[i + 1],Comment.is_banned == False, Comment.author_id.notin_((AUTOJANNY_ID,NOTIFICATIONS_ID))).count() for i in range(len(day_cutoffs) - 1)][::-1]

	plt.rcParams["figure.figsize"] = (20,20)

	signup_chart = plt.subplot2grid((20, 4), (0, 0), rowspan=5, colspan=4)
	posts_chart = plt.subplot2grid((20, 4), (7, 0), rowspan=5, colspan=4)
	comments_chart = plt.subplot2grid((20, 4), (14, 0), rowspan=5, colspan=4)

	signup_chart.grid(), posts_chart.grid(), comments_chart.grid()

	signup_chart.plot(
		daily_times,
		daily_signups,
		color='red')
	posts_chart.plot(
		daily_times,
		post_stats,
		color='green')
	comments_chart.plot(
		daily_times,
		comment_stats,
		color='gold')

	signup_chart.set_ylim(ymin=0)
	posts_chart.set_ylim(ymin=0)
	comments_chart.set_ylim(ymin=0)

	signup_chart.set_ylabel("Signups")
	posts_chart.set_ylabel("Posts")
	comments_chart.set_ylabel("Comments")
	comments_chart.set_xlabel("Time (UTC)")

	signup_chart.legend(loc='upper left', frameon=True)
	posts_chart.legend(loc='upper left', frameon=True)
	comments_chart.legend(loc='upper left', frameon=True)

	plt.savefig(file)
	plt.clf()
	return file


@app.get("/patrons")
@app.get("/paypigs")
@admin_level_required(3)
def patrons(v):
	users = g.db.query(User).filter(User.patron > 0).order_by(User.patron.desc(), User.id).all()

	return render_template("patrons.html", v=v, users=users)

@app.get("/admins")
@app.get("/badmins")
@auth_required
def admins(v):
	if v and v.admin_level > 2:
		admins = g.db.query(User).filter(User.admin_level>1).order_by(User.truecoins.desc()).all()
		admins += g.db.query(User).filter(User.admin_level==1).order_by(User.truecoins.desc()).all()
	else: admins = g.db.query(User).filter(User.admin_level>0).order_by(User.truecoins.desc()).all()
	return render_template("admins.html", v=v, admins=admins)


@app.get("/log")
@app.get("/modlog")
@auth_required
def log(v):

	page = int(request.values.get("page",1))
	admin = request.values.get("admin")
	if admin: admin_id = get_id(admin)
	else: admin_id = 0

	kind = request.values.get("kind")

	if v and v.admin_level > 1: types = ACTIONTYPES
	else: types = ACTIONTYPES2

	if kind not in types: kind = None

	actions = g.db.query(ModAction)
	if not (v and v.admin_level > 1): 
		actions = actions.filter(ModAction.kind.notin_(["shadowban","unshadowban"]))
	
	if admin_id: actions = actions.filter_by(user_id=admin_id)
	if kind: actions = actions.filter_by(kind=kind)

	actions = actions.order_by(ModAction.id.desc()).offset(25*(page-1)).limit(26).all()
	next_exists=len(actions)>25
	actions=actions[:25]

	admins = [x[0] for x in g.db.query(User.username).filter(User.admin_level > 1).all()]

	return render_template("log.html", v=v, admins=admins, types=types, admin=admin, type=kind, actions=actions, next_exists=next_exists, page=page)

@app.get("/log/<id>")
@auth_required
def log_item(id, v):

	try: id = int(id)
	except:
		try: id = int(id, 36)
		except: abort(404)

	action=g.db.query(ModAction).filter_by(id=id).one_or_none()

	if not action:
		abort(404)

	if request.path != action.permalink:
		return redirect(action.permalink)

	admins = [x[0] for x in g.db.query(User.username).filter(User.admin_level > 1).all()]

	if v and v.admin_level > 1: types = ACTIONTYPES
	else: types = ACTIONTYPES2

	return render_template("log.html", v=v, actions=[action], next_exists=False, page=1, action=action, admins=admins, types=types)

@app.get("/static/assets/favicon.ico")
def favicon():
	return send_file(f"./assets/images/{SITE_NAME}/icon.webp")

@app.get("/api")
@auth_required
def api(v):
	return render_template("api.html", v=v)

@app.get("/contact")
@app.get("/press")
@app.get("/media")
@auth_required
def contact(v):

	return render_template("contact.html", v=v)

@app.post("/send_admin")
@limiter.limit("1/second;2/minute;6/hour;10/day")
@auth_required
def submit_contact(v):
	body = request.values.get("message")
	if not body: abort(400)

	body = f'This message has been sent automatically to all admins via [/contact](/contact), user email is "{v.email}"\n\nMessage:\n\n' + body
	body_html = sanitize(body, noimages=True)

	if request.files.get("file") and request.headers.get("cf-ipcountry") != "T1":
		file=request.files["file"]
		if file.content_type.startswith('image/'):
			name = f'/images/{time.time()}'.replace('.','')[:-5] + '.webp'
			file.save(name)
			url = process_image(name)
			body_html += f'<img data-bs-target="#expandImageModal" data-bs-toggle="modal" onclick="expandDesktopImage(this.src)" class="in-comment-image" src="{url}" loading="lazy">'
		elif file.content_type.startswith('video/'):
			file.save("video.mp4")
			with open("video.mp4", 'rb') as f:
				try: url = requests.request("POST", "https://api.imgur.com/3/upload", headers={'Authorization': f'Client-ID {IMGUR_KEY}'}, files=[('video', f)]).json()['data']['link']
				except: return {"error": "Imgur error"}, 400
			if url.endswith('.'): url += 'mp4'
			body_html += f"<p>{url}</p>"
		else: return {"error": "Image/Video files only"}, 400

	send_admin(v.id, body_html)

	g.db.commit()
	return render_template("contact.html", v=v, msg="Your message has been sent.")

@app.get('/archives')
def archivesindex():
	return redirect(f"{SITE_FULL}/archives/index.html")

@app.get('/archives/<path:path>')
def archives(path):
	resp = make_response(send_from_directory('/archives', path))
	if request.path.endswith('.css'): resp.headers.add("Content-Type", "text/css")
	return resp

@app.get('/assets/<path:path>')
@app.get('/static/assets/<path:path>')
@limiter.exempt
def static_service(path):
	resp = make_response(send_from_directory('assets', path))
	if request.path.endswith('.webp') or request.path.endswith('.gif') or request.path.endswith('.ttf') or request.path.endswith('.woff') or request.path.endswith('.woff2'):
		resp.headers.remove("Cache-Control")
		resp.headers.add("Cache-Control", "public, max-age=2628000")

	if request.path.endswith('.webp'):
		resp.headers.remove("Content-Type")
		resp.headers.add("Content-Type", "image/webp")

	return resp

@app.get('/images/<path>')
@app.get('/hostedimages/<path>')
@app.get("/static/images/<path>")
@limiter.exempt
def images(path):
	resp = make_response(send_from_directory('/images', path.replace('.WEBP','.webp')))
	resp.headers.remove("Cache-Control")
	resp.headers.add("Cache-Control", "public, max-age=2628000")
	if request.path.endswith('.webp'):
		resp.headers.remove("Content-Type")
		resp.headers.add("Content-Type", "image/webp")
	return resp

@app.get("/robots.txt")
def robots_txt():
	return send_file("assets/robots.txt")


@app.get("/badges")
@auth_required
def badges(v):
	badges = g.db.query(BadgeDef).all()

	return render_template("badges.html", v=v, badges=badges)

@app.get("/blocks")
@auth_required
def blocks(v):


	blocks=g.db.query(UserBlock).all()
	users = []
	targets = []
	for x in blocks:
		users.append(get_account(x.user_id))
		targets.append(get_account(x.target_id))

	return render_template("blocks.html", v=v, users=users, targets=targets)

@app.get("/banned")
@auth_required
def banned(v):

	users = [x for x in g.db.query(User).filter(User.is_banned > 0, User.unban_utc == 0).all()]
	return render_template("banned.html", v=v, users=users)

@app.get("/formatting")
@auth_required
def formatting(v):

	return render_template("formatting.html", v=v)

@app.get("/service-worker.js")
def serviceworker():
	with open("files/assets/js/service-worker.js", "r") as f: return Response(f.read(), mimetype='application/javascript')

@app.get("/settings/security")
@auth_required
def settings_security(v):

	return render_template("settings_security.html",
						   v=v,
						   mfa_secret=pyotp.random_base32() if not v.mfa_secret else None
						   )