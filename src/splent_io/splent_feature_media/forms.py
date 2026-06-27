from flask_wtf import FlaskForm
from wtforms import SubmitField


class SplentFeatureMediaForm(FlaskForm):
    submit = SubmitField("Save splent_feature_media")
