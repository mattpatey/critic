# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2014 the Critic contributors, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

import api
import jsonapi

@jsonapi.PrimaryResource
class Reviews(object):
    """The reviews in this system."""

    name = "reviews"
    value_class = api.review.Review
    exceptions = (api.review.InvalidReviewId, api.repository.RepositoryError)

    @staticmethod
    def json(value, parameters, linked):
        """Review {
             "id": integer,
             "state": string,
             "summary": string,
             "description": string or null,
             "repository": integer,
             "branch": integer,
             "owners": integer[],
             "reviewers": integer[],
             "watchers": integer[],
             "partitions": Partition[],
           }

           Partition {
             "commits": integer[],
             "rebase": integer or null,
           }"""
        owners_ids = sorted(owner.id for owner in value.owners)
        reviewers_ids = sorted(reviewer.id for reviewer in value.reviewers)
        watchers_ids = sorted(watcher.id for watcher in value.watchers)

        linked_users = value.owners | value.reviewers | value.watchers
        linked_commits = set()
        linked_rebases = set()

        partitions = []

        def add_partition(partition):
            partition_commits = list(partition.commits.topo_ordered)
            linked_commits.update(partition_commits)
            partition_commits_ids = [commit.id for commit in partition_commits]

            if partition.following:
                partition_rebase = partition.following.rebase
                linked_rebases.add(partition_rebase)
                rebase_id = partition_rebase.id
            else:
                rebase_id = None

            partitions.append({ "commits": partition_commits_ids,
                                "rebase": rebase_id })

            if partition.following:
                add_partition(partition.following.partition)

        add_partition(value.first_partition)

        linked.add(jsonapi.v1.branches.Branches, value.branch)
        linked.add(jsonapi.v1.users.Users, *linked_users)
        linked.add(jsonapi.v1.commits.Commits, *linked_commits)
        linked.add(jsonapi.v1.rebases.Rebases, *linked_rebases)

        return parameters.filtered(
            "reviews", { "id": value.id,
                         "state": value.state,
                         "summary": value.summary,
                         "description": value.description,
                         "repository": value.repository.id,
                         "branch": value.branch.id,
                         "owners": sorted(owners_ids),
                         "reviewers": sorted(reviewers_ids),
                         "watchers": sorted(watchers_ids),
                         "partitions": partitions })

    @staticmethod
    def single(critic, argument, parameters):
        """Retrieve one (or more) reviews in this system.

           REVIEW_ID : integer

           Retrieve a review identified by its unique numeric id."""

        return Reviews.setAsContext(parameters, api.review.fetch(
            critic, review_id=jsonapi.numeric_id(argument)))

    @staticmethod
    def multiple(critic, parameters):
        """Retrieve all reviews in this system.

           repository : REPOSITORY : -

           Include only reviews in one repository, identified by the
           repository's unique numeric id or short-name.

           state : STATE[,STATE,...] : -

           Include only reviews in the specified state.  Valid values are:
           <code>open</code>, <code>closed</code>, <code>dropped</code>."""

        repository = jsonapi.v1.repositories.Repositories.deduce(
            critic, parameters)
        state_parameter = parameters.getQueryParameter("state")
        if state_parameter:
            state = set(state_parameter.split(","))
            invalid = state - api.review.Review.STATE_VALUES
            if invalid:
                raise jsonapi.UsageError(
                    "Invalid review state values: %s"
                    % ", ".join(map(repr, sorted(invalid))))
        else:
            state = None
        return api.review.fetchAll(critic, repository=repository, state=state)

    @staticmethod
    def deduce(critic, parameters):
        review = parameters.context.get("reviews")
        review_parameter = parameters.getQueryParameter("review")
        if review_parameter is not None:
            if review is not None:
                raise jsonapi.UsageError(
                    "Redundant query parameter: review=%s" % review_parameter)
            review = api.review.fetch(
                critic, review_id=jsonapi.numeric_id(review_parameter))
        return review

    @staticmethod
    def setAsContext(parameters, review):
        parameters.setContext(Reviews.name, review)
        # Also set the review's repository and branch as context.
        jsonapi.v1.repositories.Repositories.setAsContext(
            parameters, review.repository)
        jsonapi.v1.branches.Branches.setAsContext(parameters, review.branch)
        return review
