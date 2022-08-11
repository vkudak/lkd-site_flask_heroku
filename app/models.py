from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

from datetime import datetime, timedelta, timezone
import ephem

from app.star_util import t2phases, phase2str

db = SQLAlchemy()


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)

    site_name = db.Column(db.String(80), nullable=False)
    site_lat = db.Column(db.Float, nullable=False)
    site_lon = db.Column(db.Float, nullable=False)
    site_elev = db.Column(db.Float, nullable=False)

    eb_access = db.Column(db.Boolean, nullable=False, default=False)
    sat_access = db.Column(db.Boolean, nullable=False, default=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    # https://stackoverflow.com/questions/33705697/alembic-integrityerror-column-contains-null-values-when-adding-non-nullable


class Star(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    star_name = db.Column(db.String(30), nullable=False, unique=True)
    ra = db.Column(db.String(15), nullable=False)
    dec = db.Column(db.String(15), nullable=False)
    mag = db.Column(db.Float, nullable=False)
    period = db.Column(db.Float, nullable=False)
    epoch = db.Column(db.Float, nullable=False)
    n_lc_TESS = db.Column(db.Integer, nullable=False)
    publications = db.Column(db.Integer, nullable=True)
    observations = db.relationship('Observation', backref='star', cascade='all, delete, delete-orphan')
    done = db.Column(db.Boolean, nullable=False, default=False)

    def add_obs(self, start_date, end_date):
        obs = Observation(start_date=start_date, end_date=end_date, star_id=self.id)
        db.session.add(obs)
        db.session.commit()

    @classmethod
    def return_all(cls):
        """
        Return all Stars
        """
        stars = db.session.query(cls).order_by(cls.done).all()
        return stars

    @classmethod
    def delete_by_id(cls, id):
        star = db.session.query(cls).filter_by(id=id).first()
        db.session.delete(star)
        db.session.commit()

    @classmethod
    def get_by_id(cls, id):
        star = db.session.query(cls).filter_by(id=id).first()
        return star

    def rise(self, user):
        rise, _, _ = self.rise_pass_sdate(user)
        return rise

    def pas(self, user):
        _, pas, _ = self.rise_pass_sdate(user)
        return pas

    def rise_pass_sdate(self, user):
        """
        Args:
            user: user info -> lat, lon, alt

        Returns:
            risetime: String
            passtime: String
            sort_date: Timestamp (Float)
        """
        site = ephem.Observer()
        today = datetime.today()
        site.date = datetime(today.year, today.month, today.day, 23, 59, 0)  # datetime.now()
        site.lat = str(user.site_lat)  # "48.63" #loc.lat
        site.lon = str(user.site_lon)  # "22.33" #loc.lon
        site.horizon = '25'

        obj = ephem.FixedBody()
        obj.name = self.star_name
        obj._ra = ephem.hours(self.ra.replace("h", ":").replace("m", ":")[:-1])
        obj._dec = ephem.degrees(self.dec.replace("d", ":").replace("m", ":")[:-1])
        obj.compute(site)

        try:
            rise = site.previous_rising(obj)
            pas = site.next_setting(obj)
            rise_txt = str(rise).replace("/", "-")
            pass_txt = str(pas).replace("/", "-")
            sort_date = datetime.strptime(rise_txt, "%Y-%m-%d %H:%M:%S").timestamp()
        except ephem.AlwaysUpError:
            rise_txt = "alw up"
            pass_txt = "alw up"
            sort_date = (datetime.now() + timedelta(days=10)).timestamp()

        return rise_txt, pass_txt, sort_date


class Observation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Float)  # JD
    end_date = db.Column(db.Float)  # JD
    star_id = db.Column(db.Integer, db.ForeignKey('star.id'))

    def __repr__(self):
        return f'<"{self.start_date}:{self.end_date}">'

    def date0(self):
        """
        JD to python datetime and to Str
        Returns:
            Date: String
        """
        dt_offset = 2400000.500  # 1858-11-17
        dt = datetime(1858, 11, 17, tzinfo=timezone.utc) + timedelta(self.start_date - dt_offset)
        return dt.date().strftime("%Y-%m-%d")

    def phase_st(self):
        star = Star.get_by_id(self.star_id)
        return t2phases([self.start_date], star.period, star.epoch)[0]

    def phase_end(self):
        star = Star.get_by_id(self.star_id)
        return t2phases([self.end_date], star.period, star.epoch)[0]

    def asterix(self):
        star = Star.get_by_id(self.star_id)
        d_time = self.end_date - self.start_date
        if d_time >= star.period:
            return "[" + "*" * 50 + "]"
        else:
            return phase2str([self.phase_st(), self.phase_end()])


class Satellite(db.Model):
    """ Additional clas to lightcurve class"""
    id = db.Column(db.Integer, primary_key=True)
    norad = db.Column(db.Integer, nullable=False)
    cospar = db.Column(db.String(15), nullable=False)
    name = db.Column(db.String(35), nullable=False)
    # lcs = db.relationship('Lightcurve', backref='satellite', cascade='all, delete, delete-orphan')

    @classmethod
    def count_sat(cls, start=None, stop=None):
        q = db.session.query(cls).order_by(cls.norad)
        q = q.slice(start, stop)
        # if limit:
        #     q = q.limit(limit)
        # if offset:
        #     q = q.offset(offset * limit)
        sats = q.all()
        num = q.count()
        # num = db.session.query(cls).order_by(cls.norad).count()
        return sats, num

    @classmethod
    def search_sat(cls, search_string, start=None, stop=None):
        data = db.session.query(cls).filter(
                                            (db.func.lower(cls.name).ilike(search_string.lower())) |
                                            (cls.norad.ilike(search_string)) |
                                            (cls.cospar.ilike(search_string))
        )

        data = data.slice(start, stop)
        sats = data.all()
        num = data.count()
        return sats, num

    @classmethod
    def get_by_id(cls, id):
        """
        Return all Satellites
        """
        sat = db.session.query(cls).filter_by(id=id).first()
        return sat

    @classmethod
    def get_all(cls):
        """
        Return all Satellites
        """
        sats = db.session.query(cls).order_by(cls.norad).all()
        return sats

    @classmethod
    def get_by_norad(cls, norad):
        """
        Return all Satellites with defined norad number
        """
        sat = db.session.query(cls).filter_by(norad=norad).first()
        return sat

    @classmethod
    def get_by_cospar(cls, cospar):
        """
        Return all Satellites with defined COSPAR number
        """
        sat = db.session.query(cls).filter_by(cospar=cospar).first()
        return sat

    @classmethod
    def get_by_name(cls, name):
        """
        Return all Satellites with defined name
        """
        # sat = db.session.query(cls).filter_by(name=name).all()
        sats = db.session.query(cls).filter(db.func.lower(cls.name).ilike(f'%{name.replace(" ", "%")}%'.lower())).all()
        return sats

    def get_lcs(self):
        lcs = db.session.query(Lightcurve).filter(Lightcurve.sat.has(norad=self.norad)).all()
        return lcs

    def count_lcs(self):
        n = db.session.query(Lightcurve).filter(Lightcurve.sat.has(norad=self.norad)).count()
        return n


class Lightcurve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # sat_id = db.Column(db.Integer, db.ForeignKey('satellite.id'))

    sat_id = db.Column(db.Integer, db.ForeignKey('satellite.id'))
    sat = db.relationship('Satellite',
                          backref=db.backref('lightcurve', lazy='dynamic'))
    #  https://stackoverflow.com/questions/30142881/many-to-one-flask-sqlalchemy-rendering

    tle = db.Column(db.Text)  # TLE strings 0,1,2 with \n
    ut_start = db.Column(db.DateTime, nullable=False)
    ut_end = db.Column(db.DateTime, nullable=False)
    dt = db.Column(db.Float, nullable=False)
    band = db.Column(db.String(5), nullable=False)

    date_time = db.Column(db.PickleType, nullable=False)

    flux = db.Column(db.PickleType, nullable=False)
    flux_err = db.Column(db.PickleType, nullable=True)
    mag = db.Column(db.PickleType, nullable=False)
    mag_err = db.Column(db.PickleType, nullable=True)

    az = db.Column(db.PickleType, nullable=True)
    el = db.Column(db.PickleType, nullable=True)
    rg = db.Column(db.PickleType, nullable=True)

    site = db.Column(db.String(50), nullable=True)
    lsp_period = db.Column(db.Float, nullable=True)

    @classmethod
    def get_by_lc_start(cls, norad, ut_start, bands=False):
        """
        Return all LC with start_time and NORAD
        """
        # https://stackoverflow.com/questions/8561470/sqlalchemy-filtering-by-relationship-attribute
        # cls.sat.has(norad=norad),
        lcs = db.session.query(cls).filter_by(ut_start=ut_start).filter(cls.sat.has(norad=norad)).all()
        if bands:
            bands = [lc.band for lc in lcs]
            return lcs, bands
        else:
            return lcs

        # return lc

    @classmethod
    def get_by_id(cls, id):
        lc = db.session.query(cls).filter_by(id=id).first()
        return lc

